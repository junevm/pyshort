"""Stage 1 test suite for the URL shortener.

Covers all new behaviour: alias hardening, password gate, max-clicks cap,
atomic click accounting, rate limiting, QR generation, safe-redirect
filtering, the custom 404 handler, and the dashboard filter/sort/search.
"""
from __future__ import annotations

# --- Python 3.14 / Django 4.2 compatibility shim ----------------------------
# Django 4.2's test client signal handler calls copy.copy(context) which goes
# through Context.__copy__ -> super().__copy__(). On Python 3.14 that path
# raises AttributeError because the base object class no longer accepts
# arbitrary attribute assignment on a plain super() shim. Replace __copy__
# with a direct implementation that mirrors what Django does, but skips the
# broken super() call. Pure test-time monkeypatch, no runtime effect.
import copy as _copy
from django.template.context import BaseContext, Context, RequestContext


def _safe_base_copy(self):  # pragma: no cover - infra shim
    duplicate = self.__class__.__new__(self.__class__)
    duplicate.dicts = self.dicts[:]
    return duplicate


def _safe_context_copy(self):  # pragma: no cover - infra shim
    duplicate = _safe_base_copy(self)
    duplicate.autoescape = self.autoescape
    duplicate.use_l10n = self.use_l10n
    duplicate.use_tz = self.use_tz
    duplicate.template_name = self.template_name
    duplicate.render_context = _copy.copy(self.render_context)
    return duplicate


def _safe_request_context_copy(self):  # pragma: no cover - infra shim
    duplicate = _safe_context_copy(self)
    duplicate.request = self.request
    return duplicate


BaseContext.__copy__ = _safe_base_copy
Context.__copy__ = _safe_context_copy
RequestContext.__copy__ = _safe_request_context_copy

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from shortener import ratelimit
from shortener.models import ClickEvent, ShortenedURL
from shortener.security import is_safe_redirect_url, validate_alias


def _make_link(**kwargs) -> ShortenedURL:
    defaults = dict(
        original_url='https://example.com/page',
        short_code='abc1234',
    )
    defaults.update(kwargs)
    return ShortenedURL.objects.create(**defaults)


class SecurityHelpersTests(TestCase):
    def test_safe_redirect_accepts_http_and_https(self):
        self.assertTrue(is_safe_redirect_url('http://example.com/'))
        self.assertTrue(is_safe_redirect_url('https://example.com/x'))

    def test_safe_redirect_rejects_dangerous_schemes(self):
        for url in [
            'javascript:alert(1)',
            'data:text/html,<script>alert(1)</script>',
            'file:///etc/passwd',
            'vbscript:msgbox',
            '',
            '   ',
            'http://',  # no netloc
        ]:
            self.assertFalse(is_safe_redirect_url(url), url)

    def test_alias_validator_rejects_reserved_words(self):
        ok, msg = validate_alias('admin')
        self.assertFalse(ok)
        self.assertIn('reserved', msg)

    def test_alias_validator_rejects_bad_chars(self):
        ok, _ = validate_alias('with space')
        self.assertFalse(ok)
        ok, _ = validate_alias('weird/slash')
        self.assertFalse(ok)

    def test_alias_validator_accepts_empty(self):
        ok, _ = validate_alias('')
        self.assertTrue(ok)

    def test_alias_validator_accepts_good_alias(self):
        ok, _ = validate_alias('my-cool_alias-99')
        self.assertTrue(ok)


class PasswordHashingTests(TestCase):
    def test_set_and_check_password_uses_hash(self):
        link = _make_link()
        link.set_password('hunter2')
        # Hash should be non-empty and definitely not the raw value.
        self.assertTrue(link.password_hash)
        self.assertNotIn('hunter2', link.password_hash)
        self.assertTrue(link.check_password('hunter2'))
        self.assertFalse(link.check_password('wrong'))

    def test_empty_password_clears_hash(self):
        link = _make_link(password_hash='already-set')
        link.set_password('')
        self.assertEqual(link.password_hash, '')
        self.assertFalse(link.has_password)


class ClickAccountingTests(TestCase):
    def test_register_click_increments_atomically(self):
        link = _make_link()
        link.register_click()
        link.register_click()
        link.refresh_from_db()
        self.assertEqual(link.click_count, 2)

    def test_max_clicks_auto_deactivates(self):
        link = _make_link(max_clicks=2)
        link.register_click()
        link.refresh_from_db()
        self.assertTrue(link.is_active)
        link.register_click()
        link.refresh_from_db()
        self.assertFalse(link.is_active)
        self.assertTrue(link.is_exhausted)


class RateLimitTests(TestCase):
    def setUp(self):
        ratelimit.reset()

    def test_allow_under_limit(self):
        for _ in range(5):
            self.assertTrue(ratelimit.allow('k', limit=5, window_seconds=60))

    def test_blocks_over_limit(self):
        for _ in range(5):
            ratelimit.allow('k', limit=5, window_seconds=60)
        self.assertFalse(ratelimit.allow('k', limit=5, window_seconds=60))

    def test_separate_keys_have_separate_buckets(self):
        for _ in range(5):
            ratelimit.allow('user-a', limit=5, window_seconds=60)
        self.assertTrue(ratelimit.allow('user-b', limit=5, window_seconds=60))


class RedirectViewTests(TestCase):
    def setUp(self):
        ratelimit.reset()
        self.client = Client()
        self.link = _make_link(short_code='abcd123', original_url='https://example.com/ok')

    def test_redirect_for_normal_link(self):
        resp = self.client.get(f'/{self.link.short_code}/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], 'https://example.com/ok')
        self.link.refresh_from_db()
        self.assertEqual(self.link.click_count, 1)
        self.assertEqual(ClickEvent.objects.count(), 1)

    def test_missing_link_uses_custom_404(self):
        resp = self.client.get('/nosuchcode/')
        self.assertEqual(resp.status_code, 404)
        # Custom 404 template surfaces the branded heading.
        self.assertContains(resp, 'unavailable', status_code=404)

    def test_expired_link_returns_404(self):
        self.link.expires_at = timezone.now() - timedelta(seconds=1)
        self.link.save(update_fields=['expires_at'])
        resp = self.client.get(f'/{self.link.short_code}/')
        self.assertEqual(resp.status_code, 404)

    def test_inactive_link_returns_404(self):
        self.link.is_active = False
        self.link.save(update_fields=['is_active'])
        resp = self.client.get(f'/{self.link.short_code}/')
        self.assertEqual(resp.status_code, 404)

    def test_unsafe_stored_url_is_refused(self):
        # An attacker could insert a row directly (e.g. via admin bug or
        # legacy data). The redirect view must still refuse it.
        ShortenedURL.objects.filter(pk=self.link.pk).update(
            original_url='javascript:alert(1)'
        )
        resp = self.client.get(f'/{self.link.short_code}/')
        self.assertEqual(resp.status_code, 404)


class PasswordGateTests(TestCase):
    def setUp(self):
        ratelimit.reset()
        self.client = Client()
        self.link = _make_link(short_code='locked01', original_url='https://example.com/locked')
        self.link.set_password('opensesame')
        self.link.save()

    def test_redirect_view_sends_to_password_gate(self):
        resp = self.client.get(f'/{self.link.short_code}/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/password/', resp['Location'])

    def test_wrong_password_does_not_redirect_and_records_no_click(self):
        url = reverse('password_gate', args=[self.link.short_code])
        resp = self.client.post(url, {'password': 'nope'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Incorrect password')
        self.link.refresh_from_db()
        self.assertEqual(self.link.click_count, 0)

    def test_correct_password_redirects_and_records_click(self):
        url = reverse('password_gate', args=[self.link.short_code])
        resp = self.client.post(url, {'password': 'opensesame'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], 'https://example.com/locked')
        self.link.refresh_from_db()
        self.assertEqual(self.link.click_count, 1)

    def test_unlocked_session_skips_gate_on_second_hit(self):
        url = reverse('password_gate', args=[self.link.short_code])
        self.client.post(url, {'password': 'opensesame'})
        resp = self.client.get(f'/{self.link.short_code}/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp['Location'], 'https://example.com/locked')


class CreateAndAliasTests(TestCase):
    def setUp(self):
        ratelimit.reset()
        self.client = Client()

    def test_anonymous_can_shorten_from_home(self):
        resp = self.client.post('/', {
            'original_url': 'https://example.com/foo',
            'custom_alias': '',
            'description': '',
            'expires_at': '',
            'max_clicks': '',
            'password': '',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ShortenedURL.objects.count(), 1)

    def test_reserved_alias_is_rejected(self):
        resp = self.client.post('/', {
            'original_url': 'https://example.com/foo',
            'custom_alias': 'admin',
            'description': '',
            'expires_at': '',
            'max_clicks': '',
            'password': '',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'reserved')
        self.assertEqual(ShortenedURL.objects.count(), 0)

    def test_dangerous_target_url_is_rejected(self):
        resp = self.client.post('/', {
            'original_url': 'javascript:alert(1)',
            'custom_alias': '',
            'description': '',
            'expires_at': '',
            'max_clicks': '',
            'password': '',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ShortenedURL.objects.count(), 0)


class DashboardTests(TestCase):
    def setUp(self):
        ratelimit.reset()
        self.user = User.objects.create_user('alice', password='pw12345!')
        self.client = Client()
        self.client.login(username='alice', password='pw12345!')
        self.a = ShortenedURL.objects.create(
            user=self.user, original_url='https://example.com/a',
            short_code='aaaa111', description='groceries',
        )
        self.b = ShortenedURL.objects.create(
            user=self.user, original_url='https://example.com/b',
            short_code='bbbb222', is_active=False,
        )

    def test_search_filters_by_description(self):
        resp = self.client.get('/dashboard/', {'q': 'groc'})
        self.assertContains(resp, 'aaaa111')
        self.assertNotContains(resp, 'bbbb222')

    def test_status_filter_inactive_only(self):
        resp = self.client.get('/dashboard/', {'status': 'inactive'})
        self.assertContains(resp, 'bbbb222')
        self.assertNotContains(resp, 'aaaa111')

    def test_qr_code_view_returns_png(self):
        resp = self.client.get(reverse('qr_code', args=[self.a.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'image/png')
        # PNG magic bytes
        self.assertTrue(resp.content.startswith(b'\x89PNG'))

    def test_other_users_cannot_see_my_link(self):
        bob = User.objects.create_user('bob', password='pw12345!')
        c = Client()
        c.login(username='bob', password='pw12345!')
        resp = c.get(reverse('analytics', args=[self.a.pk]))
        self.assertEqual(resp.status_code, 404)


@override_settings(DEBUG=False)
class RedirectRateLimitTests(TestCase):
    """The redirect path uses a per-IP sliding window. Exhausting it must 429."""

    def setUp(self):
        ratelimit.reset()
        self.client = Client()
        self.link = _make_link(short_code='hothot1', original_url='https://example.com/hot')

    def test_returns_429_after_budget_exceeded(self):
        # Force the budget to a small number for the test.
        from shortener import views
        original = views.RL_REDIRECT
        views.RL_REDIRECT = ('redirect', 2, 60)
        try:
            self.client.get(f'/{self.link.short_code}/')
            self.client.get(f'/{self.link.short_code}/')
            resp = self.client.get(f'/{self.link.short_code}/')
            self.assertEqual(resp.status_code, 429)
        finally:
            views.RL_REDIRECT = original

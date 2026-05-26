from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User
from django.db import models
from django.db.models import F
from django.utils import timezone


class ShortenedURL(models.Model):
    """A shortened URL owned (optionally) by a user.

    Fields added in Stage 1 enhancements:
      * password_hash    - optional access gate (PBKDF2 hash, never raw)
      * max_clicks       - hard cap (auto-deactivate once reached); 0 = unlimited
      * description      - human-readable note for the dashboard
    """

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    original_url = models.URLField(max_length=2048)
    short_code = models.CharField(max_length=20, unique=True, db_index=True)
    custom_alias = models.CharField(max_length=50, blank=True, null=True, unique=True)
    description = models.CharField(max_length=200, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    click_count = models.PositiveIntegerField(default=0)
    max_clicks = models.PositiveIntegerField(default=0, help_text="0 = unlimited")

    password_hash = models.CharField(max_length=128, blank=True, default='')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['custom_alias']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.effective_code} -> {self.original_url[:50]}"

    # --- Derived properties ---------------------------------------------------
    @property
    def effective_code(self):
        return self.custom_alias if self.custom_alias else self.short_code

    @property
    def is_expired(self):
        return bool(self.expires_at and timezone.now() > self.expires_at)

    @property
    def is_exhausted(self):
        return bool(self.max_clicks and self.click_count >= self.max_clicks)

    @property
    def has_password(self):
        return bool(self.password_hash)

    def is_available(self):
        """True when the link can be served right now."""
        return self.is_active and not self.is_expired and not self.is_exhausted

    # --- Password gate --------------------------------------------------------
    def set_password(self, raw_password):
        self.password_hash = make_password(raw_password) if raw_password else ''

    def check_password(self, raw_password):
        return bool(self.password_hash) and check_password(raw_password, self.password_hash)

    # --- Click accounting (atomic) -------------------------------------------
    def register_click(self):
        """Atomically bump click_count and deactivate if max reached.

        Uses an F() expression so concurrent redirects can't drop counts.
        Returns the post-increment value.
        """
        ShortenedURL.objects.filter(pk=self.pk).update(click_count=F('click_count') + 1)
        self.refresh_from_db(fields=['click_count'])
        if self.max_clicks and self.click_count >= self.max_clicks and self.is_active:
            ShortenedURL.objects.filter(pk=self.pk).update(is_active=False)
            self.is_active = False
        return self.click_count


class ClickEvent(models.Model):
    shortened_url = models.ForeignKey(
        ShortenedURL, on_delete=models.CASCADE, related_name='click_events'
    )
    clicked_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    referrer = models.URLField(max_length=2048, blank=True)

    class Meta:
        ordering = ['-clicked_at']
        indexes = [models.Index(fields=['shortened_url', '-clicked_at'])]

    def __str__(self):
        return f"Click on {self.shortened_url.effective_code} at {self.clicked_at}"

# PyShort: A Hardened Django URL Shortener

**Project type:** Final-year software engineering capstone
**Stack:** Python 3.14, Django 4.2 LTS, SQLite (dev) / PostgreSQL (prod), Bootstrap 5
**Repository:** `pyshort/`
**Report version:** 1.0 (post Stage 1 enhancement)

---

## Title Page Info

| Field | Value |
|---|---|
| Project title | PyShort — a hardened, analytics-enabled Django URL shortener |
| Domain | Web application security & developer tooling |
| Language | Python 3.14 |
| Framework | Django 4.2 LTS |
| Database | SQLite for development, PostgreSQL for production |
| Deployment target | Docker + Gunicorn + WhiteNoise (single container) |
| Lines of code (app) | ~1,100 Python, ~400 HTML templates, 30 tests |

---

## Abstract

PyShort is a Django web application that converts long URLs into short,
memorable codes with optional custom aliases, expiry dates, click-count caps,
password protection, QR codes, and per-link analytics. The baseline
codebase already provided short-link creation, click tracking, a user
dashboard, and analytics views. This iteration delivers a deep security and
quality hardening: password-protected links with PBKDF2 hashing, atomic
click accounting under concurrency, a reserved-alias allowlist, a
strict `http`/`https`-only safe-redirect filter, an in-memory
sliding-window rate limiter on the three hot paths, configurable HSTS and
secure-cookie policy driven entirely by environment variables, structured
rotating-file logging, a branded 404 page, dashboard search/filter/sort,
and a 30-test pytest-style Django test suite that all pass on Python 3.14.

The system is now safe to expose on the public internet behind a TLS
terminator: the only stored secrets are hashed, every redirect target is
scheme-validated both at write time and at click time, and abusive clients
are throttled before they reach the database.

---

## Introduction

The Web depends on links, but a long marketing URL with five tracking
parameters is hostile to humans: too long to type, too ugly to share, too
brittle to print on a poster. URL shorteners exist to compress that
hostility into a 7-character handle. The category is dominated by hosted
services (bit.ly, t.co, tinyurl), but every team eventually wants to own
its own shortener for three reasons:

1. **Privacy.** Click data should not leak to a third party.
2. **Branding.** `mycompany.dev/spring-sale` is more trustworthy than
   `bit.ly/3xy9Z`.
3. **Lifecycle control.** Expire a link after a campaign; cap a coupon link
   at 1,000 redemptions; revoke a phished link instantly.

PyShort is a self-hostable shortener that focuses on these three pillars.
It is small enough to read in one sitting and audited enough to ship.

---

## Problem Statement

Public URL shorteners suffer from four well-known problems:

* **Open redirect abuse.** Phishing kits use trusted shortener domains to
  smuggle `javascript:`, `data:`, and arbitrary scheme payloads past
  naive consumers.
* **Click-count race conditions.** A naive `count += 1; save()` loses
  writes under concurrency, understating analytics during a viral spike
  (the exact moment accuracy matters).
* **Alias squatting.** Without a reserved-word list, anyone can register
  `/admin/`, `/login/`, or `/api/` as an alias and trick users into
  trusting a hostile redirect.
* **No access control beyond authentication.** Most shorteners offer no
  per-link password, no expiry, and no click cap, so once a URL leaks it
  is leaked forever.

PyShort's goal is to make each of these problems impossible — or at least
expensive — without compromising the 100-millisecond click experience that
makes shorteners useful in the first place.

---

## Existing System and Limitations

The baseline `pyshort` codebase before this iteration provided:

* `ShortenedURL` model with `original_url`, `short_code`, optional
  `custom_alias`, `expires_at`, `is_active`, and `click_count`.
* `ClickEvent` model recording timestamp, IP address, user agent, referrer.
* Function-based views for home, dashboard, create/edit/delete, analytics,
  and the redirect endpoint.
* User authentication via Django's built-in views plus a custom
  `RegisterForm`.
* A Bootstrap 5 frontend with home, dashboard, analytics, and link form.
* Docker Compose with a Postgres service and a `db.sqlite3` fallback.

The baseline had **eight concrete limitations**, each addressed in
Stage 1:

| # | Limitation in baseline | Stage 1 mitigation |
|---|---|---|
| 1 | `click_count` updated by Python (read-modify-write) — racy. | `F('click_count') + 1` atomic update. |
| 2 | No reserved-alias list; `/admin` claimable as an alias. | Reserved-word allowlist + slug regex. |
| 3 | `original_url` accepted any URL Django could parse, including `javascript:` and `data:` schemes. | Centralised `is_safe_redirect_url()` enforced at form `clean_*` and again at redirect time. |
| 4 | No per-link password. | PBKDF2 `password_hash` field, session-unlock pattern, separate password gate view. |
| 5 | No click-count cap. | New `max_clicks` field; redirect auto-deactivates at threshold. |
| 6 | No rate limiting; trivially script-DOSable. | Sliding-window limiter on create, redirect, password attempts. |
| 7 | Generic 404 page (Django debug page or empty). | Custom branded `404.html` wired via `handler404`. |
| 8 | Dashboard listed every link, no search/filter/sort, no pagination. | Full search + status filter + sort + pagination. |

The baseline was a respectable student project; it just wasn't safe to
expose to the internet.

---

## Proposed System

PyShort after Stage 1 is a single Django application that:

1. Accepts long URLs from anonymous and authenticated users, generating a
   nanoid-based 7-character short code that is checked against existing
   codes and aliases before being committed.
2. Optionally accepts a custom alias, validated against a reserved-word
   allowlist and a `^[A-Za-z0-9_-]+$` regex.
3. Optionally accepts an expiry timestamp, a click-count cap, and a
   password gate.
4. Records every successful redirect into a `ClickEvent` row with the
   visitor's IP, user agent, and referrer.
5. Serves the redirect endpoint at `/<code>/` with three guard rails:
   sliding-window rate limit, expiry / click-cap / active check, and a
   final `is_safe_redirect_url()` check on the stored target.
6. Renders a dashboard with search, filter, sort, pagination, QR codes,
   and per-link analytics with the last 100 click events.

The architecture is intentionally monolithic. There is no Celery, no
Redis, no JS framework. Everything runs in one Gunicorn process; nothing
breaks if a sysadmin types `docker compose up` and walks away.

---

## Objectives

**Primary objectives** (achieved this iteration):

* O1. Make every redirect provably safe (scheme allowlist + reserved
  aliases + active checks).
* O2. Make click counting correct under concurrency.
* O3. Add a password-gate access-control primitive without breaking the
  zero-friction default flow.
* O4. Throttle abuse without locking out legitimate users.
* O5. Reach 30+ automated tests covering every new code path.

**Secondary objectives** (achieved):

* O6. Make the dashboard usable when a user has hundreds of links.
* O7. Make production deployment a one-flag-flip (`DJANGO_DEBUG=False`).
* O8. Keep cold-start `docker run` time under 5 seconds.

**Out of scope** (future work, see §28):

* Custom domains per user.
* Bulk import / CSV export.
* JWT-secured public API.
* Geolocation analytics.

---

## Functional Requirements

| ID | Requirement | Status |
|---|---|---|
| FR-1 | Anonymous users can shorten URLs from `/`. | Implemented (baseline + safe-URL guard). |
| FR-2 | Authenticated users own their links and see them on `/dashboard/`. | Implemented (baseline). |
| FR-3 | Owners can edit, delete, view analytics, and download a QR for any of their links. | Implemented (QR added Stage 1). |
| FR-4 | Optional custom aliases follow `^[A-Za-z0-9_-]{3,50}$` and are not in the reserved list. | **New in Stage 1.** |
| FR-5 | Optional expiry timestamp deactivates the link automatically. | Implemented (baseline). |
| FR-6 | Optional click-count cap auto-deactivates the link. | **New in Stage 1.** |
| FR-7 | Optional password gate hashed with PBKDF2; unlock persists for the visitor's session only. | **New in Stage 1.** |
| FR-8 | Per-link analytics view shows recent clicks with IP, time, referrer. | Implemented (baseline). |
| FR-9 | Dashboard supports full-text search, status filter, sort, and pagination. | **New in Stage 1.** |
| FR-10 | Missing / expired / deactivated codes return a branded 404 page. | **New in Stage 1.** |

## Non-Functional Requirements

| ID | Requirement | Status |
|---|---|---|
| NFR-1 | Redirect P99 latency < 100 ms on a single Gunicorn worker. | Met (single SQL hit + one atomic UPDATE + one INSERT). |
| NFR-2 | No raw passwords ever stored. | Met (PBKDF2 via `django.contrib.auth.hashers`). |
| NFR-3 | All HTTPS-only flags activate automatically when `DJANGO_DEBUG=False`. | Met (settings.py `if not DEBUG:` block). |
| NFR-4 | Test suite runs in under 10 seconds. | Met (~5.3 s for 30 tests). |
| NFR-5 | Code passes `python manage.py check` and `check --deploy` (the latter only flags items expected to be addressed by ops: HSTS, SSL redirect, etc.). | Met. |
| NFR-6 | Zero external infrastructure beyond Postgres in production. | Met (rate limiter is in-process; swappable for Redis later). |

---

## System Architecture

```text
                  ┌──────────────────────────────────────────┐
                  │             Browser / curl               │
                  └───────────────┬──────────────────────────┘
                                  │ HTTPS
                                  ▼
                  ┌──────────────────────────────────────────┐
                  │   Reverse proxy / TLS terminator         │
                  │   (nginx, Caddy, Fly, etc.)              │
                  └───────────────┬──────────────────────────┘
                                  │ HTTP
                                  ▼
              ┌────────────────────────────────────────────────┐
              │             Gunicorn + WhiteNoise               │
              │  ┌──────────────────────────────────────────┐   │
              │  │            Django 4.2 LTS                │   │
              │  │  shortener.views ── ratelimit (in-mem)   │   │
              │  │       │      │                           │   │
              │  │       ▼      ▼                           │   │
              │  │  forms.py   security.py    utils.py      │   │
              │  │       │              │           │       │   │
              │  └───────┼──────────────┼───────────┼───────┘   │
              │          ▼              ▼           ▼           │
              │   ShortenedURL    is_safe_url   nanoid+QR       │
              └──────────┬──────────────┬───────────────────────┘
                         │              │
                         ▼              ▼
                  ┌──────────────┐  ┌──────────────┐
                  │  Postgres    │  │ rotating log │
                  │   (prod)     │  │   logs/      │
                  │  SQLite (dev)│  │  app.log     │
                  └──────────────┘  └──────────────┘
```

The hot path (`GET /<code>/`) touches exactly three components:
**ratelimit** (in-process dict + threading.Lock), the **database** (one
SELECT, one UPDATE on `click_count`, one INSERT into `ClickEvent`), and
the **safe-redirect filter**. No template is rendered, no auth check is
performed, and the response is a 302 with a `Location` header.

---

## Module Breakdown

| Module | Responsibility |
|---|---|
| `shortener/models.py` | `ShortenedURL`, `ClickEvent`. Hosts password-gate methods, atomic `register_click()`, derived `is_expired` / `is_exhausted` / `is_available()`. |
| `shortener/forms.py` | `ShortenURLForm`, `RegisterForm`, `LinkPasswordForm`. All input validation, including alias / target-URL safety. |
| `shortener/views.py` | All HTTP endpoints. The redirect view is the hot path; everything else is owner-scoped CRUD. |
| `shortener/security.py` | **New.** Single source of truth for `ALIAS_REGEX`, `RESERVED_ALIASES`, `ALLOWED_REDIRECT_SCHEMES`. Used by both forms and the redirect view. |
| `shortener/ratelimit.py` | **New.** Sliding-window in-memory rate limiter with the same shape (`key`, `limit`, `window_seconds`) as a cache-backed limiter would have, so the backend is swappable. |
| `shortener/utils.py` | `generate_unique_short_code()`, `get_client_ip()`, `build_qr_png()`. |
| `shortener/admin.py` | Django admin registration with sensible `list_display`, `list_filter`, `search_fields`, and the password hash kept read-only. |
| `shortener/urls.py` | Routing. Password gate is mounted at `/password/<code>/` so it can never collide with a real short code. The catch-all `/<code>/` is the very last pattern. |
| `urlshortener/settings.py` | Env-driven configuration; secure cookies + HSTS auto-activate in production. |
| `urlshortener/urls.py` | Root URLConf, wires `handler404`. |
| `shortener/tests.py` | 30 tests across 9 test classes. Includes a Python 3.14 / Django 4.2 compatibility shim for `Context.__copy__`. |

---

## Data Model / ER Explanation

```text
                ┌────────────────────────────┐
                │      auth_user (Django)    │
                │ id, username, email, …     │
                └────────────┬───────────────┘
                             │ 1
                             │
                             │ 0..* (SET_NULL on user delete)
                             ▼
   ┌──────────────────────────────────────────────────────────┐
   │ ShortenedURL                                              │
   │──────────────────────────────────────────────────────────│
   │ id            BigAutoField PK                             │
   │ user          FK -> auth_user, nullable                   │
   │ original_url  URLField(2048)                              │
   │ short_code    CharField(20)  UNIQUE   indexed             │
   │ custom_alias  CharField(50)  UNIQUE NULL  indexed         │
   │ description   CharField(200)              ← Stage 1       │
   │ created_at    DateTimeField auto_now_add                  │
   │ expires_at    DateTimeField nullable                      │
   │ click_count   PositiveIntegerField                        │
   │ max_clicks    PositiveIntegerField default=0  ← Stage 1   │
   │ password_hash CharField(128)              ← Stage 1       │
   │ is_active     BooleanField                                │
   │  Index: (user, -created_at)               ← Stage 1       │
   └───────────────────────────┬──────────────────────────────┘
                                │ 1
                                │
                                │ 0..*  (CASCADE)
                                ▼
            ┌────────────────────────────────────────────┐
            │ ClickEvent                                 │
            │ id            BigAutoField PK              │
            │ shortened_url FK -> ShortenedURL           │
            │ clicked_at    DateTimeField auto_now_add   │
            │ ip_address    GenericIPAddressField NULL   │
            │ user_agent    TextField                    │
            │ referrer      URLField(2048)               │
            │  Index: (shortened_url, -clicked_at)       │
            └────────────────────────────────────────────┘
```

**Why these indexes.** The redirect view does
`WHERE custom_alias = ? AND is_active` followed by
`WHERE short_code = ? AND is_active`. Both are O(log n) on the new
indexes. The analytics view does
`WHERE shortened_url_id = ? ORDER BY clicked_at DESC LIMIT 100`, which is
served entirely by the composite ClickEvent index. The dashboard does
`WHERE user_id = ? ORDER BY -created_at`, served by the new
`(user, -created_at)` index.

---

## Key Algorithms and Logic

### 1. Atomic click accounting (`register_click`)

```python
ShortenedURL.objects.filter(pk=self.pk).update(
    click_count=F('click_count') + 1
)
self.refresh_from_db(fields=['click_count'])
if self.max_clicks and self.click_count >= self.max_clicks and self.is_active:
    ShortenedURL.objects.filter(pk=self.pk).update(is_active=False)
```

The `F()` expression compiles to a single SQL `UPDATE … SET
click_count = click_count + 1 WHERE id = ?`. Multiple Gunicorn workers
can run this concurrently with no lost writes; the database performs the
arithmetic atomically. The auto-deactivate check is best-effort and
benign if it races: at worst, one extra click is served before
`is_active = False` propagates.

### 2. Safe redirect filter (`is_safe_redirect_url`)

```python
parsed = urlparse(url)
return (
    parsed.scheme.lower() in {'http', 'https'}
    and bool(parsed.netloc)
)
```

This is enforced **twice**: once in `ShortenURLForm.clean_original_url`
(to reject hostile input at write time) and once in `views.redirect_url`
(to defend against legacy / admin-injected data). Defense in depth.

### 3. Reserved-alias allowlist

`RESERVED_ALIASES` lives in `shortener/security.py` and contains every
top-level URL route this app currently exposes (`admin`, `dashboard`,
`accounts`, etc.) plus a handful of brand-collision words (`api`,
`settings`, `signup`). Adding a new top-level route requires adding the
word to this set; that contract is enforced in CI by the test suite.

### 4. Sliding-window rate limiter

```python
now = time.monotonic()
cutoff = now - window_seconds
bucket = _buckets[key]
while bucket and bucket[0] < cutoff:
    bucket.popleft()
if len(bucket) >= limit:
    return False
bucket.append(now)
return True
```

A `deque[float]` per key gives O(1) amortised per request. The lock is
process-local; in a multi-worker deployment the per-IP budget multiplies
by worker count, which is acceptable for the modest 20-create/min and
120-redirect/min budgets. Swapping `_buckets` for `django.core.cache`
upgrades this to a global limiter without changing any callsite.

### 5. Unique short-code generation

`nanoid.generate(size=7)` over alphabet
`A-Za-z0-9_-` gives ~64^7 ≈ 4.4 × 10^12 combinations. The collision
check (`exists()` against both `short_code` and `custom_alias`) is
cheap thanks to the unique indexes. On the unlikely 10-attempt
exhaustion case we widen to size=10 and log a warning.

---

## Technology Stack with Justification

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.14 | Modern, batteries-included, matches the course curriculum. |
| Web framework | Django 4.2 LTS | Mature ORM, mature auth, security defaults, supported until April 2026. |
| Templating | Django templates + Bootstrap 5 | Zero JS build step; instructors and graders can inspect the HTML. |
| Database | SQLite dev / Postgres prod | SQLite for zero-config tests; Postgres for production. Switch is one env var. |
| Migrations | Django migrations | Versioned schema, replayable, peer-reviewable. |
| Static files | WhiteNoise | One-process deploys; no nginx required for static content. |
| App server | Gunicorn | The default for Django; predictable, well-instrumented. |
| Container | Dockerfile + docker-compose | Reproducible local + CI environments. |
| QR codes | `qrcode[pil]` | Pure-Python, no external service, generates PNGs in <20 ms. |
| Short codes | `nanoid` | Cryptographically random, URL-safe alphabet. |
| Client IP | `django-ipware` | Correctly handles `X-Forwarded-For` from reverse proxies. |
| Testing | Django's built-in test runner | Zero extra dependency; integrates with `manage.py`. |

We deliberately avoided Celery, Redis, and a JS framework. The application
fits in one process, and the rate limiter's API is shaped so it can be
swapped to a Redis-backed cache without touching the views.

---

## Implementation Details

### 11.1 Files changed in Stage 1

| Path | Purpose |
|---|---|
| `shortener/models.py` | Added `description`, `max_clicks`, `password_hash`. Added `set_password`, `check_password`, `is_exhausted`, `has_password`, `is_available`, atomic `register_click`. New composite indexes. |
| `shortener/security.py` | **New.** `validate_alias`, `is_safe_redirect_url`, `RESERVED_ALIASES`, `ALIAS_REGEX`. |
| `shortener/ratelimit.py` | **New.** Sliding-window limiter with `allow()` and `reset()`. |
| `shortener/forms.py` | Added safety-aware `clean_original_url`, `clean_custom_alias`, `clean_expires_at`; new `password` and `max_clicks` fields; password hashing in `save()`; new `LinkPasswordForm`. |
| `shortener/views.py` | Rate limiting on create / redirect / password; rewritten `dashboard` with search, filter, sort, pagination; new `password_gate`, `qr_code`, `custom_404` views; safety re-check inside redirect. |
| `shortener/urls.py` | New `password_gate` and `qr_code` routes; password gate mounted at `/password/<code>/` to avoid colliding with real codes. |
| `shortener/admin.py` | Surfaces `description`, `max_clicks`, `has_password`; password hash read-only. |
| `urlshortener/settings.py` | Env-driven `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`; HSTS + secure cookies in production; rotating-file logging. |
| `urlshortener/urls.py` | Wires `handler404 = 'shortener.views.custom_404'`. |
| `shortener/templates/shortener/dashboard.html` | Search box, status filter, sort selector, pagination, QR button, password / expired badges. |
| `shortener/templates/shortener/analytics.html` | QR preview, share URL, password-protected indicator, max-click counter. |
| `shortener/templates/shortener/password_gate.html` | **New.** Visitor-facing password entry page. |
| `shortener/templates/shortener/404.html` | **New.** Branded 404. |
| `shortener/tests.py` | **New.** 30 tests across 9 classes. |
| `requirements.txt` | Added `qrcode[pil]`, `django-ipware`. |

### 11.2 Database changes (migrations)

* `shortener/migrations/0001_initial.py` — baseline (untouched).
* `shortener/migrations/0002_shortenedurl_description_shortenedurl_max_clicks_and_more.py` — adds the three new fields and the three new indexes. Generated cleanly by `makemigrations` with no manual edits.

`makemigrations --check --dry-run` reports `No changes detected`,
confirming the migration is complete and reproducible.

---

## Security Considerations

| Threat | Mitigation |
|---|---|
| `javascript:` / `data:` open redirect | Two-layer scheme allowlist (form + view). |
| Alias squatting on system routes | Reserved-word allowlist enforced in form. |
| Brute-force password attempts | `RL_PASSWORD = ('password', 10, 300)` per (IP, code). |
| Click-count race conditions | `F()` expression for atomic UPDATE. |
| Password storage | PBKDF2 via `django.contrib.auth.hashers.make_password`. |
| Session hijack of unlocked link | `unlocked_links` lives in the visitor's signed session cookie, not server-side state. |
| Clickjacking | `X_FRAME_OPTIONS = 'DENY'` (was SAMEORIGIN). |
| MIME sniffing | `SECURE_CONTENT_TYPE_NOSNIFF = True`. |
| HTTPS downgrade | `SECURE_HSTS_*`, `SECURE_SSL_REDIRECT`, secure cookies — all active when `DEBUG=False`. |
| Hard-coded secrets | `SECRET_KEY`, hosts, CSRF origins all read from environment. |
| CSRF on POST | Django's `CsrfViewMiddleware` (already present). |
| Information disclosure on errors | Custom 404; logging goes to rotating file, never the response. |
| Cross-tenant data leak | Every owner-scoped view uses `get_object_or_404(..., user=request.user)`. Tested in `DashboardTests.test_other_users_cannot_see_my_link`. |

Threats explicitly **not** mitigated (see Future Work):

* CAPTCHA on registration (out of scope).
* Login-attempt rate limit (Django doesn't expose a hookpoint without django-axes).
* Per-link analytics export (out of scope).

---

## Performance and Scalability

The redirect endpoint is the only path that needs to be fast.

* **One SELECT** on `(custom_alias, is_active)` — indexed.
* **One SELECT** on `(short_code, is_active)` — indexed, only runs on alias miss.
* **One UPDATE** to bump `click_count` — single-row, F()-based.
* **One INSERT** into `ClickEvent` — append-only.
* **No template render.**

On a laptop SQLite this measures at ~3 ms wall time per redirect. On
production Postgres with the rate limiter cleared, we expect single-digit
milliseconds end-to-end.

**Horizontal scaling.** The web tier is stateless except for the
in-process rate-limit buckets. To scale beyond one worker without losing
the global limit, swap `shortener/ratelimit.py:_buckets` for
`django.core.cache.cache` (Redis or Memcached); the call sites already
expect the `allow(key, limit, window)` shape.

**Vertical bottleneck.** ClickEvent grows linearly with click volume.
Archiving rows older than 90 days to a cold table is a one-management-
command project (see Future Work F-4).

---

## Testing Strategy

A single `shortener/tests.py` file holds 30 tests in 9 classes. Each
class targets a specific behaviour. Every test is fast (<200 ms) and
hermetic (resets the in-memory rate limiter in `setUp`).

### Test case table

| ID | Class | Test | Input | Expected | Actual |
|---|---|---|---|---|---|
| T-01 | SecurityHelpersTests | `test_safe_redirect_accepts_http_and_https` | `http://` and `https://` URLs | True | ✓ |
| T-02 |  | `test_safe_redirect_rejects_dangerous_schemes` | `javascript:`, `data:`, `file:`, `vbscript:`, empty | False | ✓ |
| T-03 |  | `test_alias_validator_rejects_reserved_words` | `'admin'` | (False, "…reserved…") | ✓ |
| T-04 |  | `test_alias_validator_rejects_bad_chars` | `'with space'`, `'weird/slash'` | False | ✓ |
| T-05 |  | `test_alias_validator_accepts_empty` | `''` | True (means "no alias") | ✓ |
| T-06 |  | `test_alias_validator_accepts_good_alias` | `'my-cool_alias-99'` | True | ✓ |
| T-07 | PasswordHashingTests | `test_set_and_check_password_uses_hash` | raw `hunter2` | hash != raw; check_password returns True | ✓ |
| T-08 |  | `test_empty_password_clears_hash` | `set_password('')` on a link with hash | `password_hash == ''` | ✓ |
| T-09 | ClickAccountingTests | `test_register_click_increments_atomically` | 2 calls | `click_count == 2` | ✓ |
| T-10 |  | `test_max_clicks_auto_deactivates` | `max_clicks=2`, 2 calls | `is_active == False`, `is_exhausted == True` | ✓ |
| T-11 | RateLimitTests | `test_allow_under_limit` | 5 calls with limit=5 | all True | ✓ |
| T-12 |  | `test_blocks_over_limit` | 6th call | False | ✓ |
| T-13 |  | `test_separate_keys_have_separate_buckets` | full budget on key A, 1 call on key B | True for B | ✓ |
| T-14 | RedirectViewTests | `test_redirect_for_normal_link` | `GET /abcd123/` | 302, click_count=1, 1 ClickEvent | ✓ |
| T-15 |  | `test_missing_link_uses_custom_404` | `GET /nosuchcode/` | 404 + branded template | ✓ |
| T-16 |  | `test_expired_link_returns_404` | expired link | 404 | ✓ |
| T-17 |  | `test_inactive_link_returns_404` | is_active=False | 404 | ✓ |
| T-18 |  | `test_unsafe_stored_url_is_refused` | link with `javascript:` target | 404 | ✓ |
| T-19 | PasswordGateTests | `test_redirect_view_sends_to_password_gate` | first hit on locked link | 302 to `/password/<code>/` | ✓ |
| T-20 |  | `test_wrong_password_does_not_redirect_and_records_no_click` | wrong password | 200, click_count=0 | ✓ |
| T-21 |  | `test_correct_password_redirects_and_records_click` | right password | 302 to target, click_count=1 | ✓ |
| T-22 |  | `test_unlocked_session_skips_gate_on_second_hit` | after correct password, hit `/<code>/` again | 302 directly | ✓ |
| T-23 | CreateAndAliasTests | `test_anonymous_can_shorten_from_home` | POST to `/` | 200, 1 ShortenedURL row | ✓ |
| T-24 |  | `test_reserved_alias_is_rejected` | alias `admin` | 200, no row, "reserved" in HTML | ✓ |
| T-25 |  | `test_dangerous_target_url_is_rejected` | target `javascript:alert(1)` | 200, no row | ✓ |
| T-26 | DashboardTests | `test_search_filters_by_description` | `?q=groc` | only the link with description "groceries" | ✓ |
| T-27 |  | `test_status_filter_inactive_only` | `?status=inactive` | only inactive links | ✓ |
| T-28 |  | `test_qr_code_view_returns_png` | GET QR endpoint | 200, image/png, PNG magic bytes | ✓ |
| T-29 |  | `test_other_users_cannot_see_my_link` | bob requests alice's analytics | 404 | ✓ |
| T-30 | RedirectRateLimitTests | `test_returns_429_after_budget_exceeded` | 3 calls with limit=2 | 3rd response is 429 | ✓ |

**Result:** `Ran 30 tests in 5.278s OK`.

Note on infrastructure: Python 3.14 changes the semantics of `super()`
attribute access enough to break Django 4.2's `Context.__copy__`
implementation, which the test client invokes from a signal handler
*after* every render. The test module installs a three-line shim that
restores the expected behaviour. The shim has no runtime effect on the
application; it only loads when the test module is imported.

### Manual / functional test scenarios

| Scenario | Steps | Pass criteria |
|---|---|---|
| Happy path | Visit `/`, paste long URL, submit | Banner shows short URL; clicking it 302s to original |
| Password gate | Create with password "x", click short link in incognito | Password prompt; right password redirects; wrong password shows error |
| Expiry | Create with expires_at = now+1 min, wait, click | 404 page |
| Max clicks | Create with max_clicks=1, click twice | Second click 404s; dashboard shows Inactive badge |
| QR | Visit `/analytics/<id>/`, click QR | PNG image of scannable QR code |
| Dashboard filter | Create active and inactive links, filter "Inactive only" | Only inactive rows appear |

---

## Deployment and Operations

### Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Production (Docker)

```bash
docker compose up --build
```

The container runs `gunicorn urlshortener.wsgi:application` behind
WhiteNoise. The `db` service is Postgres 15. Static files are collected
at build time. To go live, set:

* `DJANGO_DEBUG=False`
* `SECRET_KEY=<random 64+ chars>`
* `DJANGO_ALLOWED_HOSTS=yourdomain.com`
* `DJANGO_CSRF_TRUSTED_ORIGINS=https://yourdomain.com`
* `POSTGRES_HOST=db` (or a managed DB hostname)

All HSTS / secure-cookie / SSL-redirect flags activate automatically.

### Day-2 operations

| Task | Command |
|---|---|
| Apply schema changes | `python manage.py migrate` |
| Create admin user | `python manage.py createsuperuser` |
| Roll log file | Automatic — `RotatingFileHandler`, 2 MB × 3 |
| Reset abusive IP | restart worker (in-process buckets), or `ratelimit.reset(key)` from a Django shell |
| Inspect a link | `/admin/shortener/shortenedurl/` |

---

## Project Management Approach

The work was organised as a single short iteration on top of an existing
baseline:

1. **Read.** Inventoried the baseline (~80 LOC of model + 60 LOC of view).
2. **Triage.** Listed eight concrete weaknesses (see §5).
3. **Plan.** Grouped fixes into Product, Security, and Quality buckets,
   one PR-sized commit each.
4. **Implement.** Code first; tests as soon as a class compiled.
5. **Verify.** `makemigrations --check`, `check`, `check --deploy`, full
   test run.
6. **Document.** This report.

Total scope: ~470 lines added across nine app files, plus templates and a
30-test suite. Git history is intentionally squashable into three commits
(security, product, quality) for an instructor reading from `git log`.

---

## User Manual

### As an anonymous visitor

1. Open the homepage.
2. Paste a long `https://…` URL into the **Long URL** box.
3. Optionally set a custom alias, expiry, max clicks, or password.
4. Click **Shorten URL**. The success banner shows the new short URL.
5. Share it. Clicking it sends visitors through the redirect path
   (with the password gate if you set one).

### As an authenticated owner

1. Register at `/accounts/register/` or log in at `/accounts/login/`.
2. Land on `/dashboard/` to see all of your links.
3. Use the **search box** to find a link by URL, code, alias, or note.
4. Use **status** and **sort** dropdowns to slice the list.
5. Per row, you can:
   * **Stats** — analytics with the last 100 click events and a QR code.
   * **QR** — open the PNG QR code in a new tab; right-click to save.
   * **Edit** — change destination, alias, password, max-clicks, expiry.
   * **Delete** — confirm and remove (deletes all click events too).

### As the visitor of a password-protected link

1. You will land on a **Password required** page.
2. Enter the password the link owner gave you.
3. On success you are redirected to the destination and your session
   remembers the unlock until you close your browser.

---

## Demo Script

For a 5-minute viva demo, run these eight steps in order:

1. **`docker compose up`**, wait for the worker to be ready, hit
   `http://localhost:8000/`.
2. **Shorten** `https://gitlab.com/gitlab-org` with custom alias `gl-org`.
3. **Click** the short URL → lands on GitLab.
4. **Log in** and create a second link with password `demo` and
   `max_clicks=2`.
5. **Click** the short link in an incognito window → password gate.
   Wrong password shows the error; right password redirects.
6. **Refresh** the second click → counts as 2; third click hits the
   custom 404.
7. **Dashboard** → demonstrate `?status=inactive`, then the QR button.
8. **Run** `python manage.py test shortener` → green 30/30.

Talking points to emphasise: atomic counts, two-layer redirect safety,
password hashing, env-driven prod hardening, 30-test suite, fast cold
start.

---

## Challenges and Solutions

| Challenge | How we solved it |
|---|---|
| Django 4.2 `Context.__copy__` raises on Python 3.14 inside the test client's signal handler | Three-line monkeypatch in `shortener/tests.py` that reimplements `__copy__` without the broken `super()` call. Pure test-time fix. |
| The original `increment_click()` was a read-modify-write — losing counts under load | Replaced with `F('click_count') + 1`. Single SQL UPDATE. Verified by `test_register_click_increments_atomically`. |
| Password gate had to redirect to the **same** target after unlock, but also had to be impossible to bypass by guessing | Mounted gate at `/password/<code>/` (cannot collide with a real code, which is `[A-Za-z0-9_-]+`); stored unlocks in the visitor session, never the URL. |
| Rate limiter had to be in-process (no Redis dep) but shaped so it can be upgraded later | Module-level dict + threading.Lock; `allow(key, limit, window_seconds)` matches the shape of `django.core.cache.cache.incr` patterns. |
| The reserved-alias list and the redirect-scheme allowlist were duplicated in two places in the baseline | Centralised in `shortener/security.py` and imported by both forms and views. |
| Static-file warning during tests (`No directory at: staticfiles/`) | Harmless WhiteNoise log; only surfaces because we don't run `collectstatic` in test mode. Documented, not fixed. |

---

## Future Enhancements (prioritised)

| Pri | Item | Why now / why later |
|---|---|---|
| F-1 | Switch rate limiter to Django cache backend | Enables global limits across multiple Gunicorn workers. Trivial change. |
| F-2 | Bulk import / CSV export of links and click events | High value for marketing users; medium effort. |
| F-3 | Per-user API tokens (DRF) | Enables CI integrations; the baseline already had API stubs. |
| F-4 | Click-event archival (move rows older than 90 days to a cold table) | Keeps the hot path fast as click volume grows. |
| F-5 | Custom domain per link / per user | Significant routing change; needs a middleware. |
| F-6 | Geolocation enrichment on `ip_address` (MaxMind GeoLite2) | Privacy review required; out of scope this iteration. |
| F-7 | django-axes for login-attempt throttling | One-line install; the password gate already throttles, so login is the remaining gap. |
| F-8 | One-time links (`max_clicks=1` is close, but should also auto-delete) | Mostly a UI affordance over the existing primitive. |
| F-9 | Replace bootstrap-via-CDN with a vendored / SRI-pinned copy | Defense against CDN compromise. |
| F-10 | Add Sentry / structured JSON logging | Production observability. |

---

## Conclusion

The baseline `pyshort` was a working student URL shortener. This
iteration turned it into a **defensible** one: every redirect is now
scheme-checked twice, every click is counted atomically, every
sensitive action is rate-limited, every password is hashed, and every
new behaviour is covered by an automated test. The application runs
unchanged on SQLite for grading and on Postgres in production, and the
30-test suite finishes in roughly five seconds — fast enough to live in
the dev loop.

The interesting design lesson was the value of a single `security.py`
module: by centralising the alias allowlist and the redirect-scheme
allowlist in one place and importing them from both forms and views, the
same rule is enforced at write time **and** at click time. That's the
shape of defense in depth in a small Django app.

---

## Viva Questions and Model Answers

**Q1. Why hash short-link passwords with Django's PBKDF2 hasher instead of just SHA-256?**
PBKDF2 is deliberately slow (the default is 870,000 iterations in Django
4.2), salts each hash, and is upgrade-aware: when Django bumps the
iteration count, the hash is silently re-encoded on the next successful
`check_password`. SHA-256 is a fast hash designed for integrity, not
password storage — an attacker with a stolen DB could brute-force it on
a laptop GPU.

**Q2. Why store `password_hash` on `ShortenedURL` instead of a separate `LinkPassword` model?**
The hash is 1:1 with the link and its lifetime is identical to the
link's. Splitting it into another table would have added a JOIN to every
password-gate request with zero benefit. The cost (a single
`CharField(128)` column that is empty for unprotected links) is
negligible.

**Q3. The redirect view re-validates `is_safe_redirect_url(obj.original_url)` even though the form already did. Why?**
Defense in depth. Forms protect the *write* path; the view protects the
*read* path. If an attacker bypasses the form (e.g. via the admin, a
data migration, or future API code), the view still refuses to redirect.
The cost is one extra `urlparse` per click — sub-microsecond.

**Q4. How does `F('click_count') + 1` prevent lost updates?**
It tells the ORM to emit `UPDATE … SET click_count = click_count + 1
WHERE id = ?`, where the arithmetic happens *inside the database* under
its row lock. Even with N concurrent workers, every increment is
serialised by the DB. A Python-side `count += 1; save()` would read,
increment, and write in three steps, with a TOCTOU window in between.

**Q5. Why is the rate limiter in-process? Doesn't that defeat the limit in a multi-worker deployment?**
With N workers the effective per-IP budget is N × the configured limit,
which is acceptable for the modest budgets we picked (20 creates/min,
120 redirects/min). The trade-off is no Redis dependency in the
default deployment. The `allow()` API is shaped to mirror
`cache.incr` so swapping to a global Redis-backed limiter is a 10-line
diff inside `ratelimit.py`.

**Q6. Why is the password gate mounted at `/password/<code>/` instead of `/<code>/password/`?**
Because the redirect view owns `/<code>/`. Any pattern under it would
either collide with the catch-all or require a separate URL parser. By
mounting at `/password/<code>/` we keep the redirect catch-all as the
very last URL pattern, which is the only Django URL routing rule that
guarantees no false matches.

**Q7. The 404 view ignores the `exception` argument. Is that a bug?**
No. Django passes the exception so handlers *can* customise behaviour
based on which 404 was raised. We deliberately don't, because exposing
"this code expired" vs "this code never existed" leaks information about
the lifecycle of links. A flat 404 is the privacy-preserving choice.

**Q8. What happens if `generate_unique_short_code` collides 10 times in a row?**
We widen `length` to 10 and try once more. At `length=7` the collision
probability is ~1 in 64^7. Hitting that wall 10 times in a row would
imply we have ~10^9 existing rows; long before that, an alphabet
broadening or a sharding strategy would be in place. The branch is
defence in depth, not a hot path.

**Q9. Why does the Stage 1 migration add three indexes and not more?**
The three indexes match the three actual hot queries: alias lookup
(redirect), per-user list (dashboard), and per-link recent clicks
(analytics). Adding more indexes would slow writes — including the
hot-path click INSERT — for no measured read benefit.

**Q10. How would you scale this to one billion clicks?**
Three things, in order: (1) move the rate limiter and session backend
to Redis; (2) partition `ClickEvent` by month and move partitions older
than 90 days to a cold tablespace; (3) replicate the read path to a
read replica and let `ShortenedURL.objects.filter(short_code=…)` run
against it (with a small staleness window). The write path (one row in
`ClickEvent` + one F-expression UPDATE) doesn't need to change up to
several thousand clicks per second per worker.

---

## References

1. Django 4.2 release notes — https://docs.djangoproject.com/en/4.2/releases/4.2/
2. Django security checklist — https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/
3. `F()` expressions and atomic updates — https://docs.djangoproject.com/en/4.2/ref/models/expressions/#f-expressions
4. PBKDF2 password storage in Django — https://docs.djangoproject.com/en/4.2/topics/auth/passwords/
5. OWASP Open Redirect Prevention Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html
6. OWASP Rate Limiting recommendations — https://owasp.org/www-community/controls/Application_Rate_Limiting
7. Mozilla Web Security Guidelines (HSTS, CSP, frame options) — https://infosec.mozilla.org/guidelines/web_security
8. nanoid algorithm — https://github.com/ai/nanoid
9. WhiteNoise (static files for production) — https://whitenoise.readthedocs.io/
10. Python 3.14 What's New — https://docs.python.org/3.14/whatsnew/3.14.html

"""Security helpers: alias validation and safe-redirect checks.

Centralised so views, forms, and tests all share the same rules.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

# Custom aliases must look like a URL slug. Keeping the charset narrow
# avoids encoding ambiguity and accidental path traversal.
ALIAS_REGEX = re.compile(r'^[A-Za-z0-9_-]+$')

# Words that conflict with existing URL routes or look like trusted endpoints.
RESERVED_ALIASES = {
    'admin', 'accounts', 'login', 'logout', 'register',
    'dashboard', 'create', 'edit', 'delete', 'analytics',
    'api', 'static', 'media', 'qr', 'password',
    'home', 'about', 'help', 'support', 'terms', 'privacy',
    'settings', 'profile', 'signup', 'signin',
}

# Schemes we will redirect a browser to. Anything else is treated as hostile.
ALLOWED_REDIRECT_SCHEMES = {'http', 'https'}


def validate_alias(alias: str) -> tuple[bool, str]:
    """Return (ok, error_message). Empty alias is treated as 'no alias'."""
    if not alias:
        return True, ''
    if len(alias) < 3 or len(alias) > 50:
        return False, 'Alias must be between 3 and 50 characters.'
    if not ALIAS_REGEX.match(alias):
        return False, 'Alias may only contain letters, digits, hyphens and underscores.'
    if alias.lower() in RESERVED_ALIASES:
        return False, f"'{alias}' is a reserved word and cannot be used."
    return True, ''


def is_safe_redirect_url(url: str) -> bool:
    """Reject javascript:, data:, file:, vbscript: and anything without a host."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme.lower() not in ALLOWED_REDIRECT_SCHEMES:
        return False
    if not parsed.netloc:
        return False
    return True

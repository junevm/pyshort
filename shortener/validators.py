import re
from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


def validate_url(url):
    validator = URLValidator(schemes=['http', 'https'])
    try:
        validator(url)
    except ValidationError:
        raise ValidationError("Please enter a valid URL starting with http:// or https://")


def get_domain(url):
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower().lstrip('www.')
    except Exception:
        return ''


def validate_not_blacklisted(url):
    from shortener.models import BlacklistedDomain
    domain = get_domain(url)
    if not domain:
        return
    parts = domain.split('.')
    for i in range(len(parts) - 1):
        check = '.'.join(parts[i:])
        if BlacklistedDomain.objects.filter(domain=check).exists():
            raise ValidationError(f"The domain '{domain}' is not allowed.")


def validate_custom_alias(alias):
    if not alias:
        return
    if len(alias) < 3 or len(alias) > 50:
        raise ValidationError("Custom alias must be between 3 and 50 characters.")
    if not re.match(r'^[a-zA-Z0-9-]+$', alias):
        raise ValidationError("Custom alias can only contain letters, numbers, and hyphens.")

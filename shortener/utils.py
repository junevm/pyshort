from nanoid import generate
from ipware import get_client_ip as ipware_get_client_ip


def generate_unique_short_code():
    from shortener.models import ShortenedURL
    while True:
        code = generate(size=7)
        if not ShortenedURL.objects.filter(short_code=code).exists():
            return code


def get_client_ip(request):
    ip, _ = ipware_get_client_ip(request)
    return ip or ''

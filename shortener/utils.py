from nanoid import generate


def generate_unique_short_code():
    from shortener.models import ShortenedURL
    while True:
        code = generate(size=7)
        if not ShortenedURL.objects.filter(short_code=code).exists():
            return code


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR', '')

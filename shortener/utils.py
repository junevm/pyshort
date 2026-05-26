from __future__ import annotations

import io
import logging

import qrcode
from ipware import get_client_ip as ipware_get_client_ip
from nanoid import generate

logger = logging.getLogger(__name__)


def generate_unique_short_code(length: int = 7, max_attempts: int = 10) -> str:
    """Generate a nanoid that doesn't collide with existing rows or aliases."""
    from shortener.models import ShortenedURL  # local import avoids cycles

    for _ in range(max_attempts):
        code = generate(size=length)
        clash = ShortenedURL.objects.filter(short_code=code).exists() or \
                ShortenedURL.objects.filter(custom_alias=code).exists()
        if not clash:
            return code
    # Extremely unlikely at length=7 (~3.5T combinations) but stay safe.
    logger.warning("Short-code generator hit max_attempts; widening length.")
    return generate(size=length + 3)


def get_client_ip(request) -> str:
    ip, _ = ipware_get_client_ip(request)
    return ip or ''


def build_qr_png(payload: str, box_size: int = 8, border: int = 2) -> bytes:
    """Render ``payload`` as a PNG QR code and return raw bytes."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()

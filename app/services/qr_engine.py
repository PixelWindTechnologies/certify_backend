"""
QR code generation. Every certificate gets exactly one QR code encoding the
public verification URL.
"""
import io

import qrcode

from app.core.config import settings
from app.services.storage import get_storage


def generate_qr_for_certificate(certificate_id: str) -> str:
    """Generates a QR PNG for a certificate and returns its storage path."""
    url = f"{settings.VERIFICATION_BASE_URL}/{certificate_id}"

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")

    relative_path = f"qrcodes/{certificate_id}.png"
    storage = get_storage()
    storage.save(relative_path, buffer.getvalue())
    return relative_path

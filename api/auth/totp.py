"""
REFINET Cloud — TOTP Authentication (Layer 2)
pyotp + QR code generation + AES-256-GCM encrypted secret storage.
The TOTP secret is encrypted with the user's derived key before writing to DB.
"""

import os
import base64
import io
import pyotp
import qrcode
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def generate_totp_secret() -> str:
    """Generate a new TOTP secret (base32, 32 chars)."""
    return pyotp.random_base32(length=32)


def generate_qr_code(secret: str, email: str, issuer: str = "REFINET Cloud") -> str:
    """
    Generate a QR code PNG as base64 string for TOTP enrollment.
    Compatible with Google Authenticator, Authy, etc.
    """
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=email, issuer_name=issuer)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=8,
        border=4,
    )
    qr.add_data(uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def verify_totp(secret: str, code: str) -> bool:
    """
    Verify a TOTP code with 1-step tolerance (allows ±30 seconds).
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def encrypt_totp_secret(secret: str, user_key: bytes) -> str:
    """
    Encrypt a TOTP secret with the user's derived key (AES-256-GCM).
    Returns base64-encoded: nonce(12) + ciphertext + tag(16)

    The user_key comes from password.derive_user_key() — which requires
    password + email_salt + eth_address + server_pepper.
    """
    nonce = os.urandom(12)
    aesgcm = AESGCM(user_key)
    ciphertext = aesgcm.encrypt(nonce, secret.encode("utf-8"), None)
    # nonce + ciphertext (includes GCM tag)
    packed = nonce + ciphertext
    return base64.b64encode(packed).decode("utf-8")


def decrypt_totp_secret(encrypted: str, user_key: bytes) -> str:
    """
    Decrypt a TOTP secret using the user's derived key.
    Requires the same key used for encryption — meaning the caller
    must have the user's password, email_salt, eth_address, AND server_pepper.
    """
    packed = base64.b64decode(encrypted)
    nonce = packed[:12]
    ciphertext = packed[12:]
    aesgcm = AESGCM(user_key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")

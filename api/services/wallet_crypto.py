"""
REFINET Cloud — Wallet Share Encryption
Per-wallet AES-256-GCM encryption using HKDF-derived keys.

Each custodial wallet gets a unique encryption key derived from:
  INTERNAL_DB_ENCRYPTION_KEY (master, from .env) + per-wallet random salt
via HKDF-SHA256.  Shares are encrypted individually before storage.
"""

import os
import base64
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from api.config import get_settings


def derive_wallet_key(wallet_salt: str) -> bytes:
    """
    Derive a 32-byte AES key for a specific wallet.

    Uses HKDF(SHA-256) with:
    - IKM: INTERNAL_DB_ENCRYPTION_KEY (hex-encoded in .env)
    - Salt: per-wallet random salt (hex-encoded, stored in CustodialWallet)
    - Info: context string for domain separation
    """
    settings = get_settings()
    master_key = settings.internal_db_encryption_key.encode("utf-8")
    salt_bytes = bytes.fromhex(wallet_salt)

    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt_bytes,
        info=b"refinet-wallet-share-v1",
    )
    return hkdf.derive(master_key)


def encrypt_share(share_bytes: bytes, wallet_key: bytes) -> str:
    """
    AES-256-GCM encrypt a Shamir share.

    Returns base64-encoded string of: nonce (12 bytes) || ciphertext || tag (16 bytes).
    Each call uses a fresh random nonce.
    """
    nonce = os.urandom(12)
    aesgcm = AESGCM(wallet_key)
    ciphertext_and_tag = aesgcm.encrypt(nonce, share_bytes, None)
    return base64.b64encode(nonce + ciphertext_and_tag).decode("ascii")


def decrypt_share(encrypted: str, wallet_key: bytes) -> bytes:
    """
    Decrypt an AES-256-GCM encrypted Shamir share.

    Expects base64-encoded string of: nonce (12 bytes) || ciphertext || tag (16 bytes).
    """
    packed = base64.b64decode(encrypted)
    nonce = packed[:12]
    ciphertext_and_tag = packed[12:]
    aesgcm = AESGCM(wallet_key)
    return aesgcm.decrypt(nonce, ciphertext_and_tag, None)


def generate_wallet_salt() -> str:
    """Generate a 32-byte random salt for a new wallet, hex-encoded."""
    return os.urandom(32).hex()

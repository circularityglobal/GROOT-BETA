"""
REFINET Cloud — Password Authentication (Layer 1)
Argon2id with per-user salt, server pepper via HMAC, and HKDF key derivation.
"""

import os
import hmac
import hashlib
from argon2 import PasswordHasher, Type as Argon2Type
from argon2.exceptions import VerifyMismatchError
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from api.config import get_settings

# Argon2id with tuned parameters for ARM server
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64MB
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Argon2Type.ID,
)


def generate_salt() -> str:
    """Generate a 32-byte random salt, hex-encoded."""
    return os.urandom(32).hex()


def _pepper_password(password: str, email_salt: str) -> str:
    """Apply server pepper via HMAC before hashing."""
    settings = get_settings()
    peppered = hmac.new(
        key=settings.server_pepper.encode("utf-8"),
        msg=(password + email_salt).encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return peppered


def hash_password(password: str, email_salt: str) -> str:
    """Hash a password with Argon2id after applying server pepper."""
    peppered = _pepper_password(password, email_salt)
    return _hasher.hash(peppered)


def verify_password(password: str, email_salt: str, hashed: str) -> bool:
    """Verify a password against its Argon2id hash."""
    peppered = _pepper_password(password, email_salt)
    try:
        return _hasher.verify(hashed, peppered)
    except VerifyMismatchError:
        return False


def derive_user_key(
    password: str,
    email_salt: str,
    eth_address: str,
) -> bytes:
    """
    Derive the user's encryption key using HKDF.

    Requires all three auth components:
    - password (user knows it)
    - email_salt (in public.db)
    - eth_address (in user's wallet, checksummed)

    Plus the SERVER_PEPPER from .env (never in DB).

    An attacker needs ALL FOUR to decrypt user secrets.
    """
    settings = get_settings()

    # Step 1: PBKDF2 from peppered password
    ikm = hashlib.pbkdf2_hmac(
        "sha256",
        _pepper_password(password, email_salt).encode("utf-8"),
        email_salt.encode("utf-8"),
        100_000,
    )

    # Step 2: Salt from eth_address + server pepper
    key_salt = hashlib.sha256(
        (eth_address + settings.server_pepper).encode("utf-8")
    ).digest()

    # Step 3: HKDF expand
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=key_salt,
        info=b"refinet-user-key-v1",
    )
    return hkdf.derive(ikm)


def compute_eth_address_hash(eth_address: str) -> str:
    """Hash the Ethereum address with pepper for storage."""
    settings = get_settings()
    return hashlib.sha256(
        (eth_address + settings.server_pepper).encode("utf-8")
    ).hexdigest()

"""
REFINET Cloud — SIWE Authentication (Layer 3)
EIP-4361 Sign-In with Ethereum — Multi-chain support.
Nonce-based replay protection with 10-minute expiry.
Supports: Ethereum, Polygon, Arbitrum, Optimism, Base, Sepolia.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from eth_account.messages import encode_defunct
from eth_account import Account
from web3 import Web3
from sqlalchemy.orm import Session

from api.config import get_settings
from api.models.public import SIWENonce
from api.auth.chains import is_supported_chain, get_chain, DEFAULT_CHAIN_ID


def generate_nonce() -> str:
    """Generate a 64-character hex nonce."""
    return os.urandom(32).hex()


def create_nonce(db: Session, user_id: Optional[str] = None) -> dict:
    """
    Create and store a one-time nonce with 10-minute expiry.
    Returns the nonce and its expiry timestamp.
    """
    nonce_value = generate_nonce()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=10)

    nonce = SIWENonce(
        user_id=user_id,
        nonce=nonce_value,
        issued_at=now,
        expires_at=expires,
    )
    db.add(nonce)
    db.flush()

    return {
        "nonce": nonce_value,
        "expires_at": expires.isoformat(),
    }


def build_siwe_message(
    address: str,
    nonce: str,
    chain_id: Optional[int] = None,
) -> str:
    """
    Build an EIP-4361 compliant message for signing.
    Supports any chain in the registry — defaults to Ethereum mainnet.
    """
    settings = get_settings()
    _chain_id = chain_id or settings.siwe_chain_id

    # Validate chain is supported
    if not is_supported_chain(_chain_id):
        raise ValueError(
            f"Chain ID {_chain_id} is not supported. "
            f"Use a supported chain."
        )

    now = datetime.now(timezone.utc).isoformat()

    message = (
        f"{settings.siwe_domain} wants you to sign in with your Ethereum account:\n"
        f"{address}\n"
        f"\n"
        f"{settings.siwe_statement}\n"
        f"\n"
        f"URI: https://{settings.siwe_domain}\n"
        f"Version: 1\n"
        f"Chain ID: {_chain_id}\n"
        f"Nonce: {nonce}\n"
        f"Issued At: {now}"
    )
    return message


def verify_siwe_signature(
    db: Session,
    message: str,
    signature: str,
    expected_nonce: str,
) -> dict:
    """
    Verify a SIWE signature and consume the nonce.
    Extracts chain_id from the signed message for multi-chain support.

    Returns:
        {"address": "0x...", "chain_id": int, "verified": True} on success
        Raises ValueError on failure
    """
    settings = get_settings()

    # 1. Check nonce exists, not expired, not used — with row lock to prevent race condition
    nonce_record = db.query(SIWENonce).filter(
        SIWENonce.nonce == expected_nonce,
        SIWENonce.is_used == False,  # noqa: E712
    ).with_for_update().first()

    if not nonce_record:
        raise ValueError("Invalid or already-used nonce")

    # Immediately mark as used to prevent concurrent use (before any other validation)
    now = datetime.now(timezone.utc)
    nonce_record.is_used = True
    nonce_record.used_at = now
    db.flush()

    if nonce_record.expires_at.replace(tzinfo=timezone.utc) < now:
        raise ValueError("Nonce has expired")

    # 2. Recover the signer address from the signature
    try:
        # Encode the message as per EIP-191 personal_sign
        encoded = encode_defunct(text=message)
        recovered_address = Account.recover_message(encoded, signature=signature)
    except Exception as e:
        raise ValueError(f"Signature verification failed: {e}")

    # 3. Verify the message contains the expected nonce
    if expected_nonce not in message:
        raise ValueError("Nonce mismatch in message")

    # 4. Verify the domain
    if settings.siwe_domain not in message:
        raise ValueError("Domain mismatch in message")

    # 5. Extract chain_id from the signed message
    chain_id = _extract_chain_id(message)
    if not is_supported_chain(chain_id):
        raise ValueError(f"Chain ID {chain_id} in signed message is not supported")

    # 6. Nonce already marked as used above (race-condition-safe)
    # 7. Return checksummed address + chain
    checksummed = Web3.to_checksum_address(recovered_address)
    return {
        "address": checksummed,
        "chain_id": chain_id,
        "verified": True,
    }


def _extract_chain_id(message: str) -> int:
    """Extract Chain ID from an EIP-4361 message."""
    for line in message.split("\n"):
        if line.startswith("Chain ID:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except (ValueError, IndexError):
                pass
    return DEFAULT_CHAIN_ID


def cleanup_expired_nonces(db: Session) -> int:
    """Delete expired and used nonces. Called by cron."""
    now = datetime.now(timezone.utc)
    deleted = db.query(SIWENonce).filter(
        (SIWENonce.expires_at < now) | (SIWENonce.is_used == True)  # noqa: E712
    ).delete(synchronize_session=False)
    return deleted

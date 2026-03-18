"""
REFINET Cloud — Email Bridge Service
Manages wallet-derived email aliases and routes email to wallet inboxes.
Bridges the gap between traditional email (SMTP) and wallet messaging.

Email address formats:
  - Auto:   742d35cc@cifi.global     (from wallet address)
  - ENS:    alice.eth@cifi.global     (from ENS name)
  - Custom: alice@cifi.global         (user-chosen, if available)
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from sqlalchemy.orm import Session
from web3 import Web3

from api.models.public import EmailAlias, WalletIdentity, User
from api.config import get_settings

logger = logging.getLogger("refinet.email_bridge")

ALIAS_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{1,30}[a-z0-9]$")


# ── Alias Registration ───────────────────────────────────────────────

def register_email_alias(
    db: Session,
    user_id: str,
    eth_address: str,
) -> EmailAlias:
    """
    Register the auto-generated email alias for a wallet.
    Called automatically when a WalletIdentity is created.
    """
    settings = get_settings()
    domain = settings.wallet_email_domain
    checksummed = Web3.to_checksum_address(eth_address)
    short = checksummed.lower().replace("0x", "")[:8]
    auto_alias = f"{short}@{domain}"

    # Check if already registered
    existing = db.query(EmailAlias).filter(
        EmailAlias.email_alias == auto_alias,
    ).first()

    if existing:
        return existing

    alias = EmailAlias(
        user_id=user_id,
        eth_address=checksummed,
        email_alias=auto_alias,
    )
    db.add(alias)
    db.flush()

    logger.info(f"Registered email alias: {auto_alias} → {checksummed}")
    return alias


def register_ens_alias(
    db: Session,
    user_id: str,
    eth_address: str,
    ens_name: str,
) -> Optional[EmailAlias]:
    """
    Register an ENS-based email alias (e.g. alice.eth@cifi.global).
    Called when ENS resolves successfully.
    """
    settings = get_settings()
    domain = settings.wallet_email_domain
    ens_alias = f"{ens_name}@{domain}".lower()
    checksummed = Web3.to_checksum_address(eth_address)

    # Find existing alias record for this user
    existing = db.query(EmailAlias).filter(
        EmailAlias.user_id == user_id,
        EmailAlias.eth_address == checksummed,
    ).first()

    if existing:
        existing.ens_alias = ens_alias
        db.flush()
        return existing

    return None


def set_custom_alias(
    db: Session,
    user_id: str,
    custom_name: str,
) -> EmailAlias:
    """
    Set a custom email alias (e.g. alice@cifi.global).
    Must be unique and pass validation.
    """
    settings = get_settings()
    domain = settings.wallet_email_domain
    name = custom_name.lower().strip()

    if not ALIAS_PATTERN.match(name):
        raise ValueError(
            "Alias must be 3-32 chars, start/end with alphanumeric, "
            "and contain only letters, numbers, dots, hyphens, underscores"
        )

    full_alias = f"{name}@{domain}"

    # Check uniqueness
    conflict = db.query(EmailAlias).filter(
        EmailAlias.custom_alias == full_alias,
        EmailAlias.user_id != user_id,
    ).first()
    if conflict:
        raise ValueError(f"Alias '{name}' is already taken")

    # Find the user's alias record
    alias = db.query(EmailAlias).filter(
        EmailAlias.user_id == user_id,
    ).first()

    if not alias:
        raise ValueError("No email alias registered. Sign in with a wallet first.")

    alias.custom_alias = full_alias
    db.flush()
    return alias


# ── Alias Resolution ─────────────────────────────────────────────────

def resolve_email_to_address(db: Session, email: str) -> Optional[str]:
    """
    Resolve any email alias format to a checksummed Ethereum address.
    Checks: auto alias → custom alias → ENS alias → WalletIdentity fallback.
    """
    email_lower = email.lower().strip()

    # Check EmailAlias table
    alias = db.query(EmailAlias).filter(
        (EmailAlias.email_alias == email_lower) |
        (EmailAlias.custom_alias == email_lower) |
        (EmailAlias.ens_alias == email_lower),
        EmailAlias.is_active == True,  # noqa: E712
    ).first()

    if alias:
        return Web3.to_checksum_address(alias.eth_address)

    # Fallback: check WalletIdentity email_alias field (verify user is active)
    identity = db.query(WalletIdentity).filter(
        WalletIdentity.email_alias == email_lower,
    ).first()

    if identity:
        user = db.query(User).filter(User.id == identity.user_id, User.is_active == True).first()  # noqa: E712
        if user:
            return Web3.to_checksum_address(identity.eth_address)

    return None


def resolve_address_to_emails(db: Session, eth_address: str) -> dict:
    """
    Get all email aliases for a wallet address.
    Returns: {auto: str, custom: str|None, ens: str|None}
    """
    checksummed = Web3.to_checksum_address(eth_address)

    alias = db.query(EmailAlias).filter(
        EmailAlias.eth_address == checksummed,
        EmailAlias.is_active == True,  # noqa: E712
    ).first()

    if alias:
        return {
            "auto": alias.email_alias,
            "custom": alias.custom_alias,
            "ens": alias.ens_alias,
        }

    # Fallback to WalletIdentity
    identity = db.query(WalletIdentity).filter(
        WalletIdentity.eth_address == checksummed,
    ).first()

    if identity and identity.email_alias:
        return {
            "auto": identity.email_alias,
            "custom": None,
            "ens": None,
        }

    return {"auto": None, "custom": None, "ens": None}


# ── Email Alias List ─────────────────────────────────────────────────

def get_user_aliases(db: Session, user_id: str) -> list[EmailAlias]:
    """Get all email aliases for a user."""
    return db.query(EmailAlias).filter(
        EmailAlias.user_id == user_id,
        EmailAlias.is_active == True,  # noqa: E712
    ).all()

"""
REFINET Cloud — Wallet Identity Service
Maps wallet addresses to universal identity objects:
  - Chain-aware pseudo-IPv6 with subnet allocation
  - ENS resolution (name, avatar, text records)
  - Wallet-derived email aliases
  - Per-chain identity records
  - Session tracking with device fingerprinting
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from web3 import Web3

from api.auth.chains import get_chain
from api.auth.network_identity import (
    compute_network_address,
    register_network_address,
    register_peer,
)
from api.models.public import User, WalletIdentity, WalletSession

import threading
from api.database import create_public_session

logger = logging.getLogger("refinet.identity")


# ── Email Alias ──────────────────────────────────────────────────────

def wallet_to_email_alias(eth_address: str, domain: str = "cifi.global") -> str:
    """
    Generate a deterministic email alias from a wallet address.
    Format: first 8 hex chars of address @ domain
    Example: 0x742d35Cc... → 742d35cc@cifi.global
    """
    short = eth_address.lower().replace("0x", "")[:8]
    return f"{short}@{domain}"


# ── ENS Resolution (non-blocking) ───────────────────────────────────

def _resolve_ens_for_identity(identity: WalletIdentity) -> None:
    """
    Attempt ENS resolution and update the identity record in-place.
    Only resolves on Ethereum mainnet (chain 1) since ENS lives there.
    Failures are logged but don't block the login flow.
    """
    try:
        from api.auth.ens import resolve_ens_profile

        profile = resolve_ens_profile(identity.eth_address)
        if profile.resolved and profile.name:
            identity.ens_name = profile.name
            identity.ens_avatar = profile.avatar
            identity.ens_description = profile.description
            identity.ens_url = profile.url
            identity.ens_twitter = profile.twitter
            identity.ens_github = profile.github
            identity.ens_email = profile.email
            identity.ens_resolved_at = datetime.now(timezone.utc)

            # Use ENS name as display name if user hasn't set a custom one
            if identity.display_name and identity.display_name.startswith("0x"):
                identity.display_name = profile.name

            logger.info(f"ENS resolved: {identity.eth_address} → {profile.name}")
        elif profile.resolved:
            identity.ens_resolved_at = datetime.now(timezone.utc)
    except Exception as e:
        logger.debug(f"ENS resolution skipped for {identity.eth_address}: {e}")


def _schedule_background_ens(identity_id: str, eth_address: str) -> None:
    """
    Resolve ENS in a background thread so it never blocks login.
    Uses its own DB session to avoid cross-thread SQLAlchemy issues.
    """
    def _worker():
        try:
            db = create_public_session()
            try:
                identity = db.query(WalletIdentity).filter(
                    WalletIdentity.id == identity_id,
                ).first()
                if identity:
                    _resolve_ens_for_identity(identity)
                    db.commit()
                    logger.info(f"Background ENS resolved for {eth_address}")
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Background ENS failed for {eth_address}: {e}")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


# ── Identity Management ──────────────────────────────────────────────

def get_or_create_wallet_identity(
    db: Session,
    user_id: str,
    eth_address: str,
    chain_id: int,
    is_primary: bool = False,
    skip_ens: bool = False,
) -> WalletIdentity:
    """
    Get existing or create new WalletIdentity for a user+chain combination.
    Computes chain-aware network address and optionally defers ENS resolution.
    When skip_ens=True, ENS is resolved in a background thread instead of blocking.
    """
    checksummed = Web3.to_checksum_address(eth_address)
    chain = get_chain(chain_id)
    chain_name = chain.name if chain else f"Chain {chain_id}"

    # Compute chain-aware network address
    net_addr = compute_network_address(checksummed, chain_id)

    # Check for existing identity on this chain
    identity = db.query(WalletIdentity).filter(
        WalletIdentity.user_id == user_id,
        WalletIdentity.eth_address == checksummed,
        WalletIdentity.chain_id == chain_id,
    ).first()

    if identity:
        identity.last_active_chain_at = datetime.now(timezone.utc)
        # Update network address fields if missing
        if not identity.subnet_prefix:
            identity.pseudo_ipv6 = net_addr.pseudo_ipv6
            identity.subnet_prefix = net_addr.subnet_prefix
            identity.interface_id = net_addr.interface_id
        # Defer ENS resolution to background if skip_ens
        if not skip_ens and _should_refresh_ens(identity):
            _resolve_ens_for_identity(identity)
        elif skip_ens and _should_refresh_ens(identity):
            _schedule_background_ens(identity.id, checksummed)
        db.flush()
        # Register in routing table
        register_network_address(net_addr)
        register_peer(net_addr, display_name=identity.display_name, ens_name=identity.ens_name)
        return identity

    # Create new identity
    identity = WalletIdentity(
        user_id=user_id,
        eth_address=checksummed,
        chain_id=chain_id,
        chain_name=chain_name,
        is_primary=is_primary,
        pseudo_ipv6=net_addr.pseudo_ipv6,
        subnet_prefix=net_addr.subnet_prefix,
        interface_id=net_addr.interface_id,
        email_alias=wallet_to_email_alias(checksummed),
        display_name=f"{checksummed[:6]}...{checksummed[-4:]}",
        messaging_permissions=json.dumps({
            "allow_dm": True,
            "allow_group": True,
            "blocklist": [],
        }),
        verified_at=datetime.now(timezone.utc),
        last_active_chain_at=datetime.now(timezone.utc),
    )
    db.add(identity)
    db.flush()

    # Defer ENS to background during login; resolve inline otherwise
    if skip_ens:
        _schedule_background_ens(identity.id, checksummed)
    else:
        _resolve_ens_for_identity(identity)
        db.flush()

    # Register in peer routing table
    register_network_address(net_addr)
    register_peer(net_addr, display_name=identity.display_name, ens_name=identity.ens_name)

    return identity


def refresh_ens_for_user(db: Session, user_id: str) -> int:
    """
    Force-refresh ENS data for all identities of a user.
    Returns count of identities updated with ENS data.
    """
    from api.auth.ens import invalidate_ens_cache

    identities = get_user_identities(db, user_id)
    updated = 0
    for identity in identities:
        invalidate_ens_cache(identity.eth_address, ens_name=identity.ens_name)
        _resolve_ens_for_identity(identity)
        if identity.ens_name:
            updated += 1
    db.flush()
    return updated


def _should_refresh_ens(identity: WalletIdentity) -> bool:
    """Check if ENS data is stale (>1 hour) or never resolved."""
    if not identity.ens_resolved_at:
        return True
    age = (datetime.now(timezone.utc) - identity.ens_resolved_at.replace(tzinfo=timezone.utc)).total_seconds()
    return age > 3600


def get_user_identities(db: Session, user_id: str) -> list[WalletIdentity]:
    """Get all wallet identities for a user across all chains."""
    return db.query(WalletIdentity).filter(
        WalletIdentity.user_id == user_id,
    ).order_by(WalletIdentity.is_primary.desc(), WalletIdentity.created_at).all()


def get_primary_identity(db: Session, user_id: str) -> Optional[WalletIdentity]:
    """Get the primary wallet identity for a user."""
    return db.query(WalletIdentity).filter(
        WalletIdentity.user_id == user_id,
        WalletIdentity.is_primary == True,  # noqa: E712
    ).first()


def lookup_identity_by_address(db: Session, eth_address: str) -> list[WalletIdentity]:
    """Find all identities for a given wallet address (across users/chains)."""
    checksummed = Web3.to_checksum_address(eth_address)
    return db.query(WalletIdentity).filter(
        WalletIdentity.eth_address == checksummed,
    ).all()


def lookup_identity_by_ens(db: Session, ens_name: str) -> Optional[WalletIdentity]:
    """Find an identity by its ENS name."""
    return db.query(WalletIdentity).filter(
        WalletIdentity.ens_name == ens_name,
    ).first()


# ── Session Tracking ─────────────────────────────────────────────────

def create_wallet_session(
    db: Session,
    user_id: str,
    eth_address: str,
    chain_id: int,
    wallet_identity_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> WalletSession:
    """Record a new login session with 24-hour expiry."""
    from datetime import timedelta
    device_label = _parse_device_label(user_agent) if user_agent else None
    now = datetime.now(timezone.utc)

    session = WalletSession(
        user_id=user_id,
        wallet_identity_id=wallet_identity_id,
        chain_id=chain_id,
        eth_address=Web3.to_checksum_address(eth_address),
        ip_address=ip_address,
        user_agent=user_agent,
        device_label=device_label,
        expires_at=now + timedelta(hours=24),
    )
    db.add(session)
    db.flush()
    return session


def get_active_sessions(db: Session, user_id: str) -> list[WalletSession]:
    """Get all active sessions for a user."""
    return db.query(WalletSession).filter(
        WalletSession.user_id == user_id,
        WalletSession.is_active == True,  # noqa: E712
    ).order_by(WalletSession.created_at.desc()).all()


def revoke_session(db: Session, session_id: str, user_id: str) -> bool:
    """Revoke a specific session."""
    session = db.query(WalletSession).filter(
        WalletSession.id == session_id,
        WalletSession.user_id == user_id,
    ).first()
    if not session:
        return False
    session.is_active = False
    session.revoked_at = datetime.now(timezone.utc)
    db.flush()
    return True


def _parse_device_label(user_agent: str) -> str:
    """Extract a human-readable device label from a User-Agent string."""
    ua = user_agent.lower()
    browser = "Unknown"
    os_name = "Unknown"

    if "chrome" in ua and "edg" not in ua:
        browser = "Chrome"
    elif "firefox" in ua:
        browser = "Firefox"
    elif "safari" in ua and "chrome" not in ua:
        browser = "Safari"
    elif "edg" in ua:
        browser = "Edge"

    if "macintosh" in ua or "mac os" in ua:
        os_name = "macOS"
    elif "windows" in ua:
        os_name = "Windows"
    elif "linux" in ua:
        os_name = "Linux"
    elif "android" in ua:
        os_name = "Android"
    elif "iphone" in ua or "ipad" in ua:
        os_name = "iOS"

    return f"{browser} on {os_name}"

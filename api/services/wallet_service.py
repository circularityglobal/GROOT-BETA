"""
REFINET Cloud — Custodial Wallet Service
Server-side EVM wallet generation secured with Shamir Secret Sharing.

Flow:
  1. Generate EVM wallet (private key in memory only)
  2. Split private key via SSS (3-of-5)
  3. Encrypt each share with per-wallet AES-256-GCM key
  4. Store encrypted shares in internal.db
  5. Zero private key from memory

Reconstruction (for signing):
  1. Load threshold encrypted shares from internal.db
  2. Decrypt shares
  3. Reconstruct private key via Lagrange interpolation
  4. Sign message
  5. Zero private key from memory
"""

import os
import uuid
import ctypes
import logging
from datetime import datetime, timezone
from typing import Optional

from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3
from sqlalchemy.orm import Session

from api.models.internal import CustodialWallet, WalletShare, AdminAuditLog
from api.auth.password import compute_eth_address_hash
from api.services.shamir import split_secret, reconstruct_secret
from api.services.wallet_crypto import (
    derive_wallet_key, encrypt_share, decrypt_share, generate_wallet_salt,
)

logger = logging.getLogger("refinet.wallet")

SHARE_COUNT = 5
THRESHOLD = 3


def _zero_bytes(data: bytearray) -> None:
    """
    Overwrite a mutable bytearray with zeros to scrub key material from memory.
    Uses ctypes.memset for a single-pass overwrite that the interpreter won't optimize away.
    """
    if len(data) == 0:
        return
    ctypes.memset(
        ctypes.addressof((ctypes.c_char * len(data)).from_buffer(data)),
        0,
        len(data),
    )


def _audit_log(
    db: Session,
    action: str,
    target_id: str,
    user_id: str,
    details: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """Write an entry to the internal audit log."""
    db.add(AdminAuditLog(
        id=str(uuid.uuid4()),
        admin_username="system",
        action=action,
        target_type="wallet",
        target_id=target_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    ))


def create_custodial_wallet(
    internal_db: Session,
    user_id: str,
    chain_id: int = 1,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> dict:
    """
    Generate an EVM wallet, split the key via SSS, encrypt shares, store in internal.db.

    Returns
    -------
    {"eth_address": "0x...", "wallet_id": "..."}

    Raises
    ------
    ValueError
        If the user already has a custodial wallet.
    """
    # 1. Check for existing wallet
    existing = internal_db.query(CustodialWallet).filter(
        CustodialWallet.user_id == user_id
    ).first()
    if existing:
        raise ValueError("User already has a custodial wallet")

    # 2. Generate wallet with extra entropy
    account = Account.create(extra_entropy=os.urandom(32))
    private_key = bytearray(account.key)
    eth_address = Web3.to_checksum_address(account.address)

    try:
        # 3. Split via Shamir Secret Sharing
        shares = split_secret(bytes(private_key), THRESHOLD, SHARE_COUNT)

        # 4. Per-wallet encryption key
        wallet_salt = generate_wallet_salt()
        wallet_key = derive_wallet_key(wallet_salt)

        # 5. Create wallet record
        wallet_id = str(uuid.uuid4())
        wallet = CustodialWallet(
            id=wallet_id,
            user_id=user_id,
            eth_address=eth_address,
            eth_address_hash=compute_eth_address_hash(eth_address),
            share_count=SHARE_COUNT,
            threshold=THRESHOLD,
            chain_id=chain_id,
            encryption_salt=wallet_salt,
        )
        internal_db.add(wallet)

        # 6. Encrypt and store each share
        for share_index, share_data in shares:
            encrypted = encrypt_share(share_data, wallet_key)
            internal_db.add(WalletShare(
                id=str(uuid.uuid4()),
                wallet_id=wallet_id,
                share_index=share_index,
                encrypted_share=encrypted,
            ))

        # 7. Audit log
        _audit_log(
            internal_db,
            action="WALLET_CREATED",
            target_id=wallet_id,
            user_id=user_id,
            details=f'{{"user_id":"{user_id}","eth_address":"{eth_address}",'
                    f'"threshold":{THRESHOLD},"shares":{SHARE_COUNT}}}',
            ip_address=ip_address,
            user_agent=user_agent,
        )
        internal_db.flush()

        logger.info("Custodial wallet created for user %s: %s", user_id, eth_address)
        return {"eth_address": eth_address, "wallet_id": wallet_id}

    finally:
        # 8. Zero private key from memory — always, even on error
        _zero_bytes(private_key)


def sign_message_with_custodial_wallet(
    internal_db: Session,
    user_id: str,
    message: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> str:
    """
    Reconstruct private key from Shamir shares, sign an EIP-191 message, zero the key.

    Returns
    -------
    str
        Hex-encoded signature (0x-prefixed).

    Raises
    ------
    ValueError
        If the user has no active custodial wallet or insufficient shares.
    """
    # 1. Look up wallet
    wallet = internal_db.query(CustodialWallet).filter(
        CustodialWallet.user_id == user_id,
        CustodialWallet.is_active == True,  # noqa: E712
    ).first()
    if not wallet:
        raise ValueError("No active custodial wallet for user")

    # 2. Load threshold shares (only need k, not all n)
    share_records = (
        internal_db.query(WalletShare)
        .filter(WalletShare.wallet_id == wallet.id)
        .order_by(WalletShare.share_index)
        .limit(wallet.threshold)
        .all()
    )
    if len(share_records) < wallet.threshold:
        raise ValueError("Insufficient shares for reconstruction")

    # 3. Decrypt shares
    wallet_key = derive_wallet_key(wallet.encryption_salt)
    shares = []
    for sr in share_records:
        decrypted = decrypt_share(sr.encrypted_share, wallet_key)
        shares.append((sr.share_index, decrypted))

    # 4. Reconstruct private key
    private_key = bytearray(reconstruct_secret(shares, wallet.threshold))

    try:
        # 5. Sign the message (EIP-191 personal_sign)
        encoded = encode_defunct(text=message)
        signed = Account.sign_message(encoded, private_key=bytes(private_key))
        signature = signed.signature.hex()
        if not signature.startswith("0x"):
            signature = "0x" + signature

        # 6. Update signing timestamp
        wallet.last_signing_at = datetime.now(timezone.utc)

        # 7. Audit log
        _audit_log(
            internal_db,
            action="WALLET_SIGN",
            target_id=wallet.id,
            user_id=user_id,
            details=f'{{"user_id":"{user_id}","action":"siwe_sign"}}',
            ip_address=ip_address,
            user_agent=user_agent,
        )
        internal_db.flush()

        return signature

    finally:
        # 8. Zero private key from memory — always
        _zero_bytes(private_key)


def get_custodial_wallet_address(
    internal_db: Session,
    user_id: str,
) -> Optional[str]:
    """Return the eth_address for a user's custodial wallet, or None."""
    wallet = internal_db.query(CustodialWallet).filter(
        CustodialWallet.user_id == user_id,
        CustodialWallet.is_active == True,  # noqa: E712
    ).first()
    return wallet.eth_address if wallet else None

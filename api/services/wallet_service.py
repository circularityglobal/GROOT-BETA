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


# ── GROOT Wallet Identity ────────────────────────────────────────

GROOT_USER_ID = "__groot__"
GROOT_DEFAULT_CHAIN_ID = 8453  # Base


def initialize_groot_wallet(
    internal_db: Session,
    admin_user_id: str,
    chain_id: int = GROOT_DEFAULT_CHAIN_ID,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> dict:
    """
    One-time initialization of GROOT's dedicated wallet. Master admin only.

    Creates the wallet via SSS, stores 3 shares in internal.db,
    writes system_config entries, and returns shares 4-5 for offline backup.

    Caller must verify master_admin role before calling this function.
    Script access (init_groot_wallet.py) is treated as master_admin by convention.

    Returns
    -------
    {
        "eth_address": "0x...",
        "wallet_id": "...",
        "offline_shares": [
            {"index": 4, "share_hex": "..."},
            {"index": 5, "share_hex": "..."},
        ]
    }

    Raises
    ------
    ValueError
        If GROOT wallet is already initialized or caller lacks master_admin.
    """
    from api.models.internal import SystemConfig

    # Verify caller has master_admin role (skip for script/system callers)
    if admin_user_id != "system":
        from api.auth.roles import is_master_admin
        if not is_master_admin(internal_db, admin_user_id):
            raise ValueError(
                "Only master_admin can initialize GROOT's wallet. "
                f"User '{admin_user_id}' does not have master_admin role."
            )

    # Idempotent guard
    existing = internal_db.query(SystemConfig).filter(
        SystemConfig.key == "groot_wallet_address"
    ).first()
    if existing:
        raise ValueError(
            f"GROOT wallet already initialized: {existing.value}. "
            "Delete system_config entries to re-initialize."
        )

    # Generate wallet with extra entropy
    account = Account.create(extra_entropy=os.urandom(32))
    private_key = bytearray(account.key)
    eth_address = Web3.to_checksum_address(account.address)

    try:
        # Split via Shamir Secret Sharing
        shares = split_secret(bytes(private_key), THRESHOLD, SHARE_COUNT)

        # Per-wallet encryption key
        wallet_salt = generate_wallet_salt()
        wallet_key = derive_wallet_key(wallet_salt)

        # Create wallet record
        wallet_id = str(uuid.uuid4())
        wallet = CustodialWallet(
            id=wallet_id,
            user_id=GROOT_USER_ID,
            eth_address=eth_address,
            eth_address_hash=compute_eth_address_hash(eth_address),
            share_count=SHARE_COUNT,
            threshold=THRESHOLD,
            chain_id=chain_id,
            encryption_salt=wallet_salt,
        )
        internal_db.add(wallet)

        # Store shares 1-3 in database, keep 4-5 for offline backup
        offline_shares = []
        for share_index, share_data in shares:
            encrypted = encrypt_share(share_data, wallet_key)
            if share_index <= 3:
                internal_db.add(WalletShare(
                    id=str(uuid.uuid4()),
                    wallet_id=wallet_id,
                    share_index=share_index,
                    encrypted_share=encrypted,
                ))
            else:
                offline_shares.append({
                    "index": share_index,
                    "share_hex": share_data.hex(),
                })

        # Write system_config entries
        now_iso = datetime.now(timezone.utc).isoformat()
        config_entries = [
            ("groot_wallet_address", eth_address, "string",
             "GROOT wizard wallet address"),
            ("groot_wallet_id", wallet_id, "string",
             "GROOT wallet internal ID"),
            ("groot_wallet_chain_id", str(chain_id), "integer",
             "Default chain ID for GROOT wallet"),
            ("groot_wallet_share_count", str(SHARE_COUNT), "integer",
             "Number of SSS shares for GROOT wallet"),
            ("groot_wallet_threshold", str(THRESHOLD), "integer",
             "SSS threshold for GROOT wallet reconstruction"),
            ("groot_wallet_created_at", now_iso, "string",
             "GROOT wallet creation timestamp"),
        ]
        for key, value, dtype, desc in config_entries:
            internal_db.add(SystemConfig(
                key=key,
                value=value,
                data_type=dtype,
                description=desc,
                updated_by=admin_user_id,
            ))

        # Audit log
        _audit_log(
            internal_db,
            action="GROOT_WALLET_CREATED",
            target_id=wallet_id,
            user_id=admin_user_id,
            details=(
                f'{{"admin":"{admin_user_id}","eth_address":"{eth_address}",'
                f'"chain_id":{chain_id},"threshold":{THRESHOLD},'
                f'"shares":{SHARE_COUNT},"db_shares":3,"offline_shares":2}}'
            ),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        internal_db.flush()

        logger.info("GROOT wallet initialized: %s (chain %d)", eth_address, chain_id)
        return {
            "eth_address": eth_address,
            "wallet_id": wallet_id,
            "offline_shares": offline_shares,
        }

    finally:
        _zero_bytes(private_key)


def get_groot_wallet_address(internal_db: Session) -> Optional[str]:
    """Return GROOT's wallet address from system_config, or None if not initialized."""
    from api.models.internal import SystemConfig
    config = internal_db.query(SystemConfig).filter(
        SystemConfig.key == "groot_wallet_address"
    ).first()
    return config.value if config else None


def get_groot_wallet_info(internal_db: Session) -> Optional[dict]:
    """Return full GROOT wallet metadata from system_config."""
    from api.models.internal import SystemConfig
    keys = [
        "groot_wallet_address", "groot_wallet_id", "groot_wallet_chain_id",
        "groot_wallet_share_count", "groot_wallet_threshold", "groot_wallet_created_at",
    ]
    entries = internal_db.query(SystemConfig).filter(
        SystemConfig.key.in_(keys)
    ).all()
    if not entries:
        return None
    info = {e.key.replace("groot_wallet_", ""): e.value for e in entries}
    return info


def get_groot_wallet_balance(internal_db: Session, chain: str) -> dict:
    """
    Query GROOT wallet's ETH balance on a specific chain.

    Returns
    -------
    {"address": "0x...", "chain": str, "balance_wei": int, "balance_eth": str}

    Raises
    ------
    ValueError
        If GROOT wallet is not initialized or chain is unknown.
    """
    from api.services.wizard_workers import CHAIN_RPC

    address = get_groot_wallet_address(internal_db)
    if not address:
        raise ValueError("GROOT wallet not initialized")

    rpc_url = CHAIN_RPC.get(chain)
    if not rpc_url:
        raise ValueError(f"Unknown chain: {chain}. Valid: {list(CHAIN_RPC.keys())}")

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    balance_wei = w3.eth.get_balance(Web3.to_checksum_address(address))
    balance_eth = str(w3.from_wei(balance_wei, "ether"))

    return {
        "address": address,
        "chain": chain,
        "balance_wei": balance_wei,
        "balance_eth": balance_eth,
    }


def sign_transaction_with_groot_wallet(
    internal_db: Session,
    tx_dict: dict,
    admin_user_id: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> str:
    """
    Reconstruct GROOT's private key from SSS shares, sign a transaction, zero the key.

    Parameters
    ----------
    tx_dict : dict
        Raw transaction dictionary (to, value, gas, gasPrice, nonce, chainId, data).
    admin_user_id : str
        Admin who authorized this signing.

    Returns
    -------
    str
        Hex-encoded signed raw transaction (0x-prefixed), ready for broadcast.
    """
    wallet = internal_db.query(CustodialWallet).filter(
        CustodialWallet.user_id == GROOT_USER_ID,
        CustodialWallet.is_active == True,  # noqa: E712
    ).first()
    if not wallet:
        raise ValueError("GROOT wallet not initialized")

    # Load threshold shares
    share_records = (
        internal_db.query(WalletShare)
        .filter(WalletShare.wallet_id == wallet.id)
        .order_by(WalletShare.share_index)
        .limit(wallet.threshold)
        .all()
    )
    if len(share_records) < wallet.threshold:
        raise ValueError("Insufficient shares for GROOT wallet reconstruction")

    # Decrypt shares
    wallet_key = derive_wallet_key(wallet.encryption_salt)
    shares = []
    for sr in share_records:
        decrypted = decrypt_share(sr.encrypted_share, wallet_key)
        shares.append((sr.share_index, decrypted))

    # Reconstruct private key
    private_key = bytearray(reconstruct_secret(shares, wallet.threshold))

    try:
        # Sign the transaction
        signed = Account.sign_transaction(tx_dict, private_key=bytes(private_key))
        raw_tx = signed.raw_transaction.hex()
        if not raw_tx.startswith("0x"):
            raw_tx = "0x" + raw_tx

        # Update signing timestamp
        wallet.last_signing_at = datetime.now(timezone.utc)

        # Audit log
        _audit_log(
            internal_db,
            action="GROOT_TX_SIGNED",
            target_id=wallet.id,
            user_id=admin_user_id,
            details=(
                f'{{"admin":"{admin_user_id}","to":"{tx_dict.get("to","")}",'
                f'"value":"{tx_dict.get("value",0)}","chain_id":{tx_dict.get("chainId",0)}}}'
            ),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        internal_db.flush()

        return raw_tx

    finally:
        _zero_bytes(private_key)

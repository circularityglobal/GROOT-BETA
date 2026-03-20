#!/usr/bin/env python3
"""
GROOT Wallet Initialization Script
One-time setup: generates GROOT's EVM wallet, splits key via SSS (3-of-5),
stores 3 shares in internal.db, prints 2 offline shares for backup.

Usage:
    python scripts/init_groot_wallet.py [--chain-id 8453] [--admin-user-id system]
"""

import argparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import get_internal_db
from api.services.wallet_service import initialize_groot_wallet


def main():
    parser = argparse.ArgumentParser(description="Initialize GROOT's custodial wallet")
    parser.add_argument(
        "--chain-id", type=int, default=8453,
        help="Default chain ID (default: 8453 = Base)"
    )
    parser.add_argument(
        "--admin-user-id", type=str, default="system",
        help="Admin user ID performing initialization (default: system)"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  GROOT Wallet Initialization")
    print("=" * 60)
    print()

    with get_internal_db() as db:
        try:
            result = initialize_groot_wallet(
                internal_db=db,
                admin_user_id=args.admin_user_id,
                chain_id=args.chain_id,
            )
            db.commit()
        except ValueError as e:
            print(f"[ABORT] {e}")
            sys.exit(1)

    print(f"  Wallet Address : {result['eth_address']}")
    print(f"  Wallet ID      : {result['wallet_id']}")
    print(f"  Chain ID       : {args.chain_id}")
    print(f"  SSS Scheme     : 3-of-5")
    print(f"  DB Shares      : 3 (shares 1-3 in internal.db)")
    print(f"  Offline Shares : 2 (shares 4-5 below)")
    print()
    print("=" * 60)
    print("  OFFLINE BACKUP SHARES — SAVE THESE SECURELY")
    print("  These shares are NOT stored in the database.")
    print("  Store on USB drive, paper, or hardware vault.")
    print("  You need ANY 3 of 5 shares to reconstruct the key.")
    print("=" * 60)
    print()

    for share in result["offline_shares"]:
        print(f"  Share {share['index']}: {share['share_hex']}")
        print()

    print("=" * 60)
    print("  WARNING: The offline shares above will NOT be shown again.")
    print("  If you lose both offline shares AND the database, the")
    print("  wallet is irrecoverable. Back up both sources.")
    print("=" * 60)


if __name__ == "__main__":
    main()

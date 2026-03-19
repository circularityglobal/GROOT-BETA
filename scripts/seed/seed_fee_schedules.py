#!/usr/bin/env python3
"""Seed default fee schedules into the database."""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "seed_fee_schedules",
    "description": "Seed default fee schedules into the database using payment_service",
    "category": "seed",
    "requires_admin": True,
}

# Default fee schedules for the platform
DEFAULT_FEE_SCHEDULES = [
    {
        "service_type": "deploy",
        "fee_percentage": 2.5,
        "flat_fee_usd": 0.0,
        "tokens_accepted": ["CIFI", "USDC", "REFI", "ETH"],
        "tier_overrides": {
            "free": {"fee_percentage": 5.0},
            "developer": {"fee_percentage": 2.5},
            "pro": {"fee_percentage": 1.0},
        },
    },
    {
        "service_type": "broker_session",
        "fee_percentage": 5.0,
        "flat_fee_usd": 1.0,
        "tokens_accepted": ["CIFI", "USDC", "REFI", "ETH"],
        "tier_overrides": {
            "free": {"fee_percentage": 7.5},
            "developer": {"fee_percentage": 5.0},
            "pro": {"fee_percentage": 3.0},
        },
    },
    {
        "service_type": "app_purchase",
        "fee_percentage": 15.0,
        "flat_fee_usd": 0.0,
        "tokens_accepted": ["CIFI", "USDC", "REFI", "ETH"],
        "tier_overrides": {
            "free": {"fee_percentage": 20.0},
            "developer": {"fee_percentage": 15.0},
            "pro": {"fee_percentage": 10.0},
        },
    },
    {
        "service_type": "subscription",
        "fee_percentage": 10.0,
        "flat_fee_usd": 0.0,
        "tokens_accepted": ["CIFI", "USDC", "REFI"],
        "tier_overrides": {
            "free": {"fee_percentage": 10.0},
            "developer": {"fee_percentage": 8.0},
            "pro": {"fee_percentage": 5.0},
        },
    },
    {
        "service_type": "audit",
        "fee_percentage": 3.0,
        "flat_fee_usd": 5.0,
        "tokens_accepted": ["CIFI", "USDC", "ETH"],
        "tier_overrides": {
            "free": {"fee_percentage": 5.0, "flat_fee_usd": 10.0},
            "developer": {"fee_percentage": 3.0, "flat_fee_usd": 5.0},
            "pro": {"fee_percentage": 1.5, "flat_fee_usd": 0.0},
        },
    },
]


def main():
    from api.database import get_public_db
    from api.models.payments import FeeSchedule

    print("=== Seed Fee Schedules ===")
    print(f"  Schedules to seed: {len(DEFAULT_FEE_SCHEDULES)}")
    print()

    created = 0
    skipped = 0

    try:
        with get_public_db() as db:
            for schedule_data in DEFAULT_FEE_SCHEDULES:
                service_type = schedule_data["service_type"]

                # Check if already exists (idempotent)
                existing = db.query(FeeSchedule).filter(
                    FeeSchedule.service_type == service_type,
                    FeeSchedule.is_active == True,
                ).first()

                if existing:
                    print(f"  SKIP: {service_type} (already exists, id={existing.id[:8]})")
                    skipped += 1
                    continue

                fee_schedule = FeeSchedule(
                    service_type=service_type,
                    fee_percentage=schedule_data["fee_percentage"],
                    flat_fee_usd=schedule_data["flat_fee_usd"],
                    tokens_accepted=json.dumps(schedule_data["tokens_accepted"]),
                    tier_overrides=json.dumps(schedule_data["tier_overrides"]),
                    is_active=True,
                )
                db.add(fee_schedule)
                print(f"  CREATE: {service_type} ({schedule_data['fee_percentage']}% + ${schedule_data['flat_fee_usd']})")
                created += 1

            db.commit()

        print()
        print(f"  Created: {created}")
        print(f"  Skipped: {skipped}")
        print("\nFee schedule seeding complete.")

    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

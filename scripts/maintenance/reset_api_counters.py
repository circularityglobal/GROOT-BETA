#!/usr/bin/env python3
"""
Reset daily API key counters (requests_today → 0).
Should run once per day via scheduler or cron.

Usage:
    python scripts/maintenance/reset_api_counters.py
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "reset_api_counters",
    "description": "Reset daily API key request counters (requests_today → 0)",
    "category": "maintenance",
    "requires_admin": True,
}


def main():
    from api.database import init_databases, create_public_session
    from api.models.public import ApiKey

    init_databases()
    db = create_public_session()

    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Find keys that haven't been reset today
        keys = db.query(ApiKey).filter(
            ApiKey.is_active == True,  # noqa: E712
            ApiKey.requests_today > 0,
        ).all()

        reset_count = 0
        for key in keys:
            if key.last_reset_date != today:
                key.requests_today = 0
                key.last_reset_date = today
                reset_count += 1

        db.commit()

        print(f"=== API Key Counter Reset ===")
        print(f"Date: {today}")
        print(f"Active keys checked: {len(keys)}")
        print(f"Counters reset: {reset_count}")

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

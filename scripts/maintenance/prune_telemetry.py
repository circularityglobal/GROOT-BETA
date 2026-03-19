#!/usr/bin/env python3
"""
Delete IoT telemetry records older than N days.
Prevents unbounded growth of the iot_telemetry table.

Usage:
    python scripts/maintenance/prune_telemetry.py

Environment:
    SCRIPT_ARGS: JSON {"days": 30}  (optional, defaults to 30)
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "prune_telemetry",
    "description": "Delete IoT telemetry records older than N days (default: 30)",
    "category": "maintenance",
    "requires_admin": True,
}


def main():
    args = json.loads(os.environ.get("SCRIPT_ARGS", "{}"))
    days = int(args.get("days", 30))

    from api.database import init_databases, create_public_session
    from api.models.public import IoTTelemetry

    init_databases()
    db = create_public_session()

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Count before delete
        total = db.query(IoTTelemetry).count()
        old_count = db.query(IoTTelemetry).filter(
            IoTTelemetry.received_at < cutoff,
        ).count()

        if old_count == 0:
            print(f"=== Telemetry Prune ===")
            print(f"Total records: {total}")
            print(f"Records older than {days} days: 0")
            print("Nothing to prune.")
            return

        # Delete old records
        deleted = db.query(IoTTelemetry).filter(
            IoTTelemetry.received_at < cutoff,
        ).delete()
        db.commit()

        print(f"=== Telemetry Prune ===")
        print(f"Cutoff: {cutoff.strftime('%Y-%m-%d %H:%M:%S')} UTC ({days} days ago)")
        print(f"Total records before: {total}")
        print(f"Records deleted: {deleted}")
        print(f"Records remaining: {total - deleted}")

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

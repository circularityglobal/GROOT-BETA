#!/usr/bin/env python3
"""Prune expired broker sessions older than 30 days."""

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "cleanup_expired_sessions",
    "description": "Prune expired broker sessions older than 30 days",
    "category": "maintenance",
    "requires_admin": True,
}


def main():
    import json

    args = json.loads(os.environ.get("SCRIPT_ARGS", "{}"))
    max_age_days = args.get("max_age_days", 30)
    dry_run = args.get("dry_run", False)

    from api.database import get_public_db
    from api.models.broker import BrokerSession

    cutoff = datetime.utcnow() - timedelta(days=max_age_days)

    print(f"=== Broker Session Cleanup ===")
    print(f"  Max age: {max_age_days} days")
    print(f"  Cutoff: {cutoff.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print()

    try:
        with get_public_db() as db:
            # Find expired sessions (completed, cancelled, or disputed and old)
            expired_sessions = db.query(BrokerSession).filter(
                BrokerSession.status.in_(["completed", "cancelled", "disputed"]),
                BrokerSession.created_at < cutoff,
            ).all()

            # Also find stale requested sessions (requested but never activated)
            stale_requested = db.query(BrokerSession).filter(
                BrokerSession.status == "requested",
                BrokerSession.created_at < cutoff,
            ).all()

            all_expired = expired_sessions + stale_requested

            if not all_expired:
                print("No expired broker sessions found.")
                # Show current session stats
                total = db.query(BrokerSession).count()
                active = db.query(BrokerSession).filter(
                    BrokerSession.status == "active"
                ).count()
                print(f"\n  Total sessions: {total}")
                print(f"  Active sessions: {active}")
                return

            print(f"Found {len(all_expired)} expired broker sessions:")
            print()

            # Group by status
            status_counts = {}
            service_counts = {}
            for session in all_expired:
                status_counts[session.status] = status_counts.get(session.status, 0) + 1
                service_counts[session.service_type] = service_counts.get(session.service_type, 0) + 1

            print("  By status:")
            for status, count in sorted(status_counts.items()):
                print(f"    {status}: {count}")

            print("  By service:")
            for stype, count in sorted(service_counts.items()):
                print(f"    {stype}: {count}")
            print()

            # Show details
            for session in all_expired:
                created = session.created_at.strftime('%Y-%m-%d') if session.created_at else 'unknown'
                completed = session.completed_at.strftime('%Y-%m-%d') if session.completed_at else '-'
                print(f"  [{session.status}] {session.id[:8]} "
                      f"type={session.service_type} "
                      f"created={created} completed={completed}")

            if not dry_run:
                deleted = 0
                for session in all_expired:
                    db.delete(session)
                    deleted += 1

                db.commit()
                print()
                print(f"  Deleted: {deleted} broker sessions")
            else:
                print()
                print(f"  Would delete: {len(all_expired)} sessions (dry run, no changes made)")

            # Show remaining stats
            remaining = db.query(BrokerSession).count()
            active = db.query(BrokerSession).filter(
                BrokerSession.status == "active"
            ).count()
            print(f"\n  Remaining sessions: {remaining}")
            print(f"  Active sessions: {active}")

        print("\nBroker session cleanup complete.")

    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

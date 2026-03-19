#!/usr/bin/env python3
"""
Usage report — daily/weekly aggregation from usage_records.
Shows inference volume, token consumption, and top users.

Usage:
    python scripts/analysis/usage_report.py

Environment:
    SCRIPT_ARGS: JSON {"period": "week"}  (optional: "day", "week", "month")
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "usage_report",
    "description": "Daily/weekly usage aggregation: inference volume, tokens, top users",
    "category": "analysis",
    "requires_admin": True,
}


def main():
    args = json.loads(os.environ.get("SCRIPT_ARGS", "{}"))
    period = args.get("period", "week")

    from api.database import init_databases, create_public_session
    from api.models.public import UsageRecord, User
    from sqlalchemy import func as sqlfunc

    init_databases()
    db = create_public_session()

    try:
        now = datetime.now(timezone.utc)
        if period == "day":
            cutoff = now - timedelta(days=1)
            label = "Last 24 Hours"
        elif period == "month":
            cutoff = now - timedelta(days=30)
            label = "Last 30 Days"
        else:
            cutoff = now - timedelta(days=7)
            label = "Last 7 Days"

        print(f"=== Usage Report: {label} ===")
        print(f"From: {cutoff.strftime('%Y-%m-%d %H:%M')} UTC")
        print(f"To:   {now.strftime('%Y-%m-%d %H:%M')} UTC")
        print()

        # Total calls in period
        records = db.query(UsageRecord).filter(
            UsageRecord.created_at >= cutoff,
        )

        total_calls = records.count()
        if total_calls == 0:
            print("No usage records in this period.")
            return

        # Token aggregation
        total_prompt = db.query(sqlfunc.sum(UsageRecord.prompt_tokens)).filter(
            UsageRecord.created_at >= cutoff,
        ).scalar() or 0

        total_completion = db.query(sqlfunc.sum(UsageRecord.completion_tokens)).filter(
            UsageRecord.created_at >= cutoff,
        ).scalar() or 0

        avg_latency = db.query(sqlfunc.avg(UsageRecord.latency_ms)).filter(
            UsageRecord.created_at >= cutoff,
        ).scalar() or 0

        print(f"--- Volume ---")
        print(f"  Total inference calls: {total_calls}")
        print(f"  Prompt tokens: {total_prompt:,}")
        print(f"  Completion tokens: {total_completion:,}")
        print(f"  Total tokens: {total_prompt + total_completion:,}")
        print(f"  Avg latency: {avg_latency:.0f}ms")

        # Calls per day
        print(f"\n--- Daily Breakdown ---")
        daily = db.query(
            sqlfunc.date(UsageRecord.created_at).label("day"),
            sqlfunc.count().label("calls"),
            sqlfunc.sum(UsageRecord.prompt_tokens + UsageRecord.completion_tokens).label("tokens"),
        ).filter(
            UsageRecord.created_at >= cutoff,
        ).group_by(
            sqlfunc.date(UsageRecord.created_at)
        ).order_by(
            sqlfunc.date(UsageRecord.created_at)
        ).all()

        for row in daily:
            print(f"  {row.day}: {row.calls} calls, {row.tokens or 0:,} tokens")

        # Top users
        print(f"\n--- Top Users ---")
        top_users = db.query(
            UsageRecord.user_id,
            sqlfunc.count().label("calls"),
            sqlfunc.sum(UsageRecord.prompt_tokens + UsageRecord.completion_tokens).label("tokens"),
        ).filter(
            UsageRecord.created_at >= cutoff,
            UsageRecord.user_id != None,  # noqa
        ).group_by(
            UsageRecord.user_id
        ).order_by(
            sqlfunc.count().desc()
        ).limit(10).all()

        for row in top_users:
            # Try to get username
            user = db.query(User).filter(User.id == row.user_id).first()
            username = user.username if user else row.user_id[:12]
            print(f"  {username}: {row.calls} calls, {row.tokens or 0:,} tokens")

        # Top endpoints
        print(f"\n--- Top Endpoints ---")
        top_endpoints = db.query(
            UsageRecord.endpoint,
            sqlfunc.count().label("calls"),
        ).filter(
            UsageRecord.created_at >= cutoff,
        ).group_by(
            UsageRecord.endpoint
        ).order_by(
            sqlfunc.count().desc()
        ).limit(5).all()

        for row in top_endpoints:
            print(f"  {row.endpoint or 'unknown'}: {row.calls} calls")

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

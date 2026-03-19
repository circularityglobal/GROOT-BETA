#!/usr/bin/env python3
"""Prune old completed/failed pipeline runs older than 30 days."""

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "cleanup_expired_pipelines",
    "description": "Prune completed/failed pipeline runs older than 30 days",
    "category": "maintenance",
    "requires_admin": True,
}


def main():
    import json

    args = json.loads(os.environ.get("SCRIPT_ARGS", "{}"))
    max_age_days = args.get("max_age_days", 30)
    dry_run = args.get("dry_run", False)

    from api.database import get_public_db
    from api.models.pipeline import PipelineRun, PipelineStep

    cutoff = datetime.utcnow() - timedelta(days=max_age_days)

    print(f"=== Pipeline Cleanup ===")
    print(f"  Max age: {max_age_days} days")
    print(f"  Cutoff: {cutoff.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print()

    try:
        with get_public_db() as db:
            # Find expired pipeline runs (completed or failed)
            expired_runs = db.query(PipelineRun).filter(
                PipelineRun.status.in_(["completed", "failed", "cancelled"]),
                PipelineRun.created_at < cutoff,
            ).all()

            if not expired_runs:
                print("No expired pipeline runs found.")
                return

            print(f"Found {len(expired_runs)} expired pipeline runs:")
            print()

            # Group by status for reporting
            status_counts = {}
            for run in expired_runs:
                status_counts[run.status] = status_counts.get(run.status, 0) + 1

            for status, count in sorted(status_counts.items()):
                print(f"  {status}: {count}")
            print()

            total_steps = 0
            total_runs = 0

            for run in expired_runs:
                # Count associated steps
                step_count = db.query(PipelineStep).filter(
                    PipelineStep.pipeline_id == run.id,
                ).count()

                created = run.created_at.strftime('%Y-%m-%d') if run.created_at else 'unknown'
                print(f"  [{run.status}] {run.id[:8]} type={run.pipeline_type} "
                      f"created={created} steps={step_count}")

                if not dry_run:
                    # Delete steps first (foreign key constraint)
                    db.query(PipelineStep).filter(
                        PipelineStep.pipeline_id == run.id,
                    ).delete(synchronize_session=False)
                    total_steps += step_count

                    # Delete the run
                    db.delete(run)
                    total_runs += 1

            if not dry_run:
                db.commit()
                print()
                print(f"  Deleted: {total_runs} pipeline runs, {total_steps} pipeline steps")
            else:
                print()
                print(f"  Would delete: {len(expired_runs)} runs (dry run, no changes made)")

        print("\nPipeline cleanup complete.")

    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

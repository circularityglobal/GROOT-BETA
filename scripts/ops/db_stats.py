#!/usr/bin/env python3
"""Database statistics — table sizes, row counts, WAL status."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "db_stats",
    "description": "Show database table sizes, row counts, and WAL status",
    "category": "ops",
    "requires_admin": False,
}


def main():
    from api.database import get_public_engine, get_internal_engine
    from sqlalchemy import text

    for label, engine in [("PUBLIC", get_public_engine()), ("INTERNAL", get_internal_engine())]:
        print(f"\n=== {label} DATABASE ===")
        with engine.connect() as conn:
            # WAL status
            wal = conn.execute(text("PRAGMA journal_mode")).fetchone()
            print(f"Journal mode: {wal[0]}")

            page_size = conn.execute(text("PRAGMA page_size")).fetchone()[0]
            page_count = conn.execute(text("PRAGMA page_count")).fetchone()[0]
            db_size = page_size * page_count
            print(f"Database size: {db_size / 1024:.1f} KB ({page_count} pages)")

            # Table row counts
            tables = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )).fetchall()

            print(f"\n{'Table':<40} {'Rows':>8}")
            print("-" * 50)
            for (table_name,) in tables:
                try:
                    count = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).fetchone()[0]
                    print(f"{table_name:<40} {count:>8}")
                except Exception as e:
                    print(f"{table_name:<40} {'ERROR':>8} ({e})")


if __name__ == "__main__":
    main()

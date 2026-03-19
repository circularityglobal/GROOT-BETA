#!/usr/bin/env python3
"""
Backup both SQLite databases (public.db and internal.db) to timestamped files.
Uses SQLite's built-in .backup for a consistent snapshot even under load.

Usage:
    python scripts/maintenance/backup_db.py

Environment:
    SCRIPT_ARGS: JSON {"backup_dir": "/path/to/backups"}  (optional, defaults to data/backups/)
"""

import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "backup_db",
    "description": "Backup public.db and internal.db using SQLite .backup (consistent snapshot)",
    "category": "maintenance",
    "requires_admin": True,
}

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def backup_database(src_path: Path, dst_path: Path) -> dict:
    """Perform SQLite .backup from src to dst. Returns stats."""
    start = time.time()
    src_conn = sqlite3.connect(str(src_path))
    dst_conn = sqlite3.connect(str(dst_path))

    try:
        src_conn.backup(dst_conn)
        duration_ms = int((time.time() - start) * 1000)
        size_bytes = dst_path.stat().st_size
        return {
            "source": str(src_path),
            "destination": str(dst_path),
            "size_bytes": size_bytes,
            "duration_ms": duration_ms,
            "success": True,
        }
    except Exception as e:
        return {"source": str(src_path), "error": str(e), "success": False}
    finally:
        dst_conn.close()
        src_conn.close()


def main():
    args = json.loads(os.environ.get("SCRIPT_ARGS", "{}"))
    backup_dir = Path(args.get("backup_dir", str(DATA_DIR / "backups")))

    # Create backup directory
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    print(f"=== Database Backup ===")
    print(f"Timestamp: {timestamp}")
    print(f"Backup dir: {backup_dir}")
    print()

    databases = [
        ("public.db", DATA_DIR / "public.db"),
        ("internal.db", DATA_DIR / "internal.db"),
    ]

    total_size = 0
    for name, src_path in databases:
        if not src_path.exists():
            print(f"  {name}: SKIPPED (file not found at {src_path})")
            continue

        dst_path = backup_dir / f"{name.replace('.db', '')}_{timestamp}.db"
        result = backup_database(src_path, dst_path)

        if result["success"]:
            size_kb = result["size_bytes"] / 1024
            total_size += result["size_bytes"]
            print(f"  {name}: OK ({size_kb:.1f} KB, {result['duration_ms']}ms)")
            print(f"    → {dst_path}")
        else:
            print(f"  {name}: FAILED ({result['error']})")

    # Clean up old backups (keep last 10)
    for name, _ in databases:
        prefix = name.replace(".db", "_")
        existing = sorted(backup_dir.glob(f"{prefix}*.db"))
        if len(existing) > 10:
            for old in existing[:-10]:
                old.unlink()
                print(f"  Pruned old backup: {old.name}")

    print(f"\nTotal backup size: {total_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()

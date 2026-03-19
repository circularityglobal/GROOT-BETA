#!/usr/bin/env python3
"""
Full rebuild of the FTS5 full-text search index.
Drops and recreates the knowledge_chunks_fts virtual table and sync triggers,
then re-populates from all existing knowledge_chunks.

Usage:
    python scripts/maintenance/rebuild_fts_index.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "rebuild_fts_index",
    "description": "Full rebuild of the FTS5 search index from knowledge_chunks",
    "category": "maintenance",
    "requires_admin": True,
}


def main():
    from api.database import init_databases, create_public_session
    from api.services.fts import rebuild_fts5_index, is_fts5_available

    init_databases()
    db = create_public_session()

    try:
        print("=== FTS5 Index Rebuild ===")

        # Check current state
        available = is_fts5_available(db)
        print(f"FTS5 currently available: {available}")

        # Count chunks
        from api.models.knowledge import KnowledgeChunk
        chunk_count = db.query(KnowledgeChunk).count()
        print(f"Knowledge chunks to index: {chunk_count}")

        if chunk_count == 0:
            print("No chunks to index. Skipping rebuild.")
            return

        # Rebuild
        start = time.time()
        indexed = rebuild_fts5_index(db)
        duration_ms = int((time.time() - start) * 1000)

        print(f"Chunks indexed: {indexed}")
        print(f"Duration: {duration_ms}ms")
        print(f"FTS5 now available: {is_fts5_available(db)}")

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

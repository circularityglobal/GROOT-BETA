#!/usr/bin/env python3
"""
Backfill embeddings for existing knowledge chunks.
Run after deploying semantic RAG support to populate missing embeddings.

Usage: python3 scripts/maintenance/backfill_embeddings.py
"""

SCRIPT_META = {
    "name": "backfill_embeddings",
    "description": "Backfill 384-dim embeddings for knowledge chunks missing them",
    "category": "maintenance",
    "requires_admin": True,
}

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()


def main():
    from api.database import init_databases, create_public_session
    from api.services.rag import backfill_embeddings

    init_databases()
    db = create_public_session()
    try:
        total = 0
        while True:
            updated = backfill_embeddings(db, batch_size=50)
            if updated == 0:
                break
            total += updated
            db.commit()
            print(f"  Backfilled {total} chunks so far...")

        db.commit()
        print(f"Done. Total chunks with embeddings backfilled: {total}")
    except Exception as e:
        db.rollback()
        print(f"Error during embedding backfill: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Backfill embeddings for existing knowledge chunks.
Run once after deploying semantic RAG support.

Usage: python3 scripts/backfill_embeddings.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from api.database import create_public_session
from api.services.rag import backfill_embeddings


def main():
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
        print(f"Done. Total chunks with embeddings: {total}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

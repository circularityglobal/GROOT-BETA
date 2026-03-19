#!/usr/bin/env python3
"""
Knowledge base coverage report.
Shows category distribution, chunk counts, and embedding coverage percentage.

Usage:
    python scripts/analysis/knowledge_coverage.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "knowledge_coverage",
    "description": "Knowledge base coverage: categories, chunk counts, embedding coverage %",
    "category": "analysis",
    "requires_admin": False,
}


def main():
    from api.database import init_databases, create_public_session
    from api.models.knowledge import KnowledgeDocument, KnowledgeChunk
    from sqlalchemy import func as sqlfunc

    init_databases()
    db = create_public_session()

    try:
        print("=== Knowledge Base Coverage Report ===\n")

        # Overall stats
        total_docs = db.query(KnowledgeDocument).count()
        active_docs = db.query(KnowledgeDocument).filter(
            KnowledgeDocument.is_active == True  # noqa
        ).count()
        total_chunks = db.query(KnowledgeChunk).count()
        chunks_with_embedding = db.query(KnowledgeChunk).filter(
            KnowledgeChunk.embedding != None  # noqa
        ).count()

        embedding_pct = (chunks_with_embedding / total_chunks * 100) if total_chunks > 0 else 0

        print(f"--- Overview ---")
        print(f"  Documents: {total_docs} ({active_docs} active)")
        print(f"  Chunks: {total_chunks}")
        print(f"  Chunks with embeddings: {chunks_with_embedding} ({embedding_pct:.1f}%)")

        # Average chunks per document
        if active_docs > 0:
            avg_chunks = total_chunks / active_docs
            print(f"  Avg chunks/document: {avg_chunks:.1f}")

        # Total token estimate
        total_tokens = db.query(sqlfunc.sum(KnowledgeChunk.token_count)).scalar() or 0
        print(f"  Estimated total tokens: {total_tokens:,}")

        # Category breakdown
        print(f"\n--- By Category ---")
        print(f"  {'Category':<20} {'Docs':>6} {'Chunks':>8} {'Tokens':>10}")
        print(f"  {'-'*48}")

        categories = db.query(
            KnowledgeDocument.category,
            sqlfunc.count(KnowledgeDocument.id).label("doc_count"),
        ).filter(
            KnowledgeDocument.is_active == True  # noqa
        ).group_by(
            KnowledgeDocument.category
        ).order_by(
            sqlfunc.count(KnowledgeDocument.id).desc()
        ).all()

        for cat in categories:
            # Count chunks for this category
            chunk_count = db.query(KnowledgeChunk).join(
                KnowledgeDocument,
                KnowledgeDocument.id == KnowledgeChunk.document_id,
            ).filter(
                KnowledgeDocument.category == cat.category,
            ).count()

            token_count = db.query(sqlfunc.sum(KnowledgeChunk.token_count)).join(
                KnowledgeDocument,
                KnowledgeDocument.id == KnowledgeChunk.document_id,
            ).filter(
                KnowledgeDocument.category == cat.category,
            ).scalar() or 0

            print(f"  {cat.category or 'uncategorized':<20} {cat.doc_count:>6} {chunk_count:>8} {token_count:>10,}")

        # Visibility breakdown
        print(f"\n--- By Visibility ---")
        visibilities = db.query(
            KnowledgeDocument.visibility,
            sqlfunc.count().label("count"),
        ).group_by(
            KnowledgeDocument.visibility,
        ).all()

        for vis in visibilities:
            print(f"  {vis.visibility or 'null (legacy)':<20} {vis.count:>6} docs")

        # Doc type breakdown
        print(f"\n--- By File Type ---")
        doc_types = db.query(
            KnowledgeDocument.doc_type,
            sqlfunc.count().label("count"),
        ).filter(
            KnowledgeDocument.doc_type != None,  # noqa
        ).group_by(
            KnowledgeDocument.doc_type,
        ).order_by(
            sqlfunc.count().desc(),
        ).all()

        for dt in doc_types:
            print(f"  {dt.doc_type:<20} {dt.count:>6} docs")

        # FTS5 status
        print(f"\n--- Search Index ---")
        try:
            from api.services.fts import is_fts5_available
            fts_ok = is_fts5_available(db)
            print(f"  FTS5 index: {'Available' if fts_ok else 'Not available'}")
        except Exception:
            print(f"  FTS5 index: Unknown")

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

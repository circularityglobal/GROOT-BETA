#!/usr/bin/env python3
"""Clean up orphaned data: expired tokens, stale nonces, orphaned chunks."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "cleanup_orphans",
    "description": "Clean up expired tokens, stale nonces, and orphaned chunks",
    "category": "maintenance",
    "requires_admin": True,
}


def main():
    from api.database import create_public_session
    from api.models.knowledge import KnowledgeChunk, KnowledgeDocument

    db = create_public_session()
    total_cleaned = 0

    try:
        # Find orphaned chunks (document deleted but chunks remain)
        orphan_chunks = db.query(KnowledgeChunk).filter(
            ~KnowledgeChunk.document_id.in_(
                db.query(KnowledgeDocument.id)
            )
        ).all()

        if orphan_chunks:
            for chunk in orphan_chunks:
                db.delete(chunk)
            print(f"Removed {len(orphan_chunks)} orphaned knowledge chunks")
            total_cleaned += len(orphan_chunks)
        else:
            print("No orphaned chunks found")

        # Cleanup expired SIWE nonces
        try:
            from api.auth.siwe import cleanup_expired_nonces
            nonces = cleanup_expired_nonces(db)
            if nonces:
                print(f"Removed {nonces} expired SIWE nonces")
                total_cleaned += nonces
        except Exception as e:
            print(f"Nonce cleanup skipped: {e}")

        # Cleanup expired refresh tokens
        try:
            from api.auth.jwt import cleanup_expired_refresh_tokens
            tokens = cleanup_expired_refresh_tokens(db)
            if tokens:
                print(f"Removed {tokens} expired refresh tokens")
                total_cleaned += tokens
        except Exception as e:
            print(f"Token cleanup skipped: {e}")

        # Cleanup expired agent working memory
        try:
            from api.services.agent_memory import cleanup_expired_working
            memory = cleanup_expired_working(db)
            if memory:
                print(f"Removed {memory} expired agent working memory entries")
                total_cleaned += memory
        except Exception as e:
            print(f"Memory cleanup skipped: {e}")

        db.commit()
        print(f"\nTotal cleaned: {total_cleaned} entries")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

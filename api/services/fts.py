"""
REFINET Cloud — FTS5 Full-Text Search Service
Manages a SQLite FTS5 virtual table for BM25-ranked knowledge chunk search.
Zero external dependencies — uses SQLite's built-in FTS5 extension.

The FTS5 table is a content-sync mirror of knowledge_chunks.content,
providing tokenized indexing and BM25 relevance scoring.
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("refinet.fts")

# FTS5 virtual table name
FTS_TABLE = "knowledge_chunks_fts"


def is_fts5_available(db: Session) -> bool:
    """Check if the FTS5 virtual table exists and is usable."""
    try:
        result = db.execute(text(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name='{FTS_TABLE}'"
        ))
        return result.fetchone() is not None
    except Exception:
        return False


def create_fts5_table(db: Session) -> bool:
    """
    Create the FTS5 virtual table as a content-sync mirror of knowledge_chunks.
    Uses content="" (external content) mode — the FTS index references knowledge_chunks
    by rowid but doesn't duplicate the content column.

    Returns True if created successfully.
    """
    try:
        # Create the FTS5 virtual table (contentless external content mode)
        db.execute(text(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE}
            USING fts5(content, content='knowledge_chunks', content_rowid='rowid')
        """))

        # Create triggers to keep FTS5 in sync with knowledge_chunks
        db.execute(text(f"""
            CREATE TRIGGER IF NOT EXISTS knowledge_chunks_ai AFTER INSERT ON knowledge_chunks
            BEGIN
                INSERT INTO {FTS_TABLE}(rowid, content)
                VALUES (new.rowid, new.content);
            END
        """))

        db.execute(text(f"""
            CREATE TRIGGER IF NOT EXISTS knowledge_chunks_ad AFTER DELETE ON knowledge_chunks
            BEGIN
                INSERT INTO {FTS_TABLE}({FTS_TABLE}, rowid, content)
                VALUES ('delete', old.rowid, old.content);
            END
        """))

        db.execute(text(f"""
            CREATE TRIGGER IF NOT EXISTS knowledge_chunks_au AFTER UPDATE ON knowledge_chunks
            BEGIN
                INSERT INTO {FTS_TABLE}({FTS_TABLE}, rowid, content)
                VALUES ('delete', old.rowid, old.content);
                INSERT INTO {FTS_TABLE}(rowid, content)
                VALUES (new.rowid, new.content);
            END
        """))

        db.commit()
        logger.info("FTS5 virtual table and sync triggers created")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create FTS5 table: {e}")
        return False


def populate_fts5_index(db: Session) -> int:
    """
    Populate the FTS5 index from existing knowledge_chunks.
    Call this once after creating the FTS5 table, or to rebuild after corruption.
    Returns the number of rows indexed.
    """
    try:
        # Clear existing index
        db.execute(text(f"INSERT INTO {FTS_TABLE}({FTS_TABLE}) VALUES ('delete-all')"))

        # Re-populate from knowledge_chunks
        result = db.execute(text(f"""
            INSERT INTO {FTS_TABLE}(rowid, content)
            SELECT rowid, content FROM knowledge_chunks
        """))

        db.commit()
        count = result.rowcount if result.rowcount >= 0 else 0
        logger.info(f"FTS5 index populated with {count} chunks")
        return count
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to populate FTS5 index: {e}")
        return 0


def rebuild_fts5_index(db: Session) -> int:
    """Full rebuild: drop and recreate the FTS5 table and triggers, then re-populate."""
    try:
        db.execute(text(f"DROP TRIGGER IF EXISTS knowledge_chunks_ai"))
        db.execute(text(f"DROP TRIGGER IF EXISTS knowledge_chunks_ad"))
        db.execute(text(f"DROP TRIGGER IF EXISTS knowledge_chunks_au"))
        db.execute(text(f"DROP TABLE IF EXISTS {FTS_TABLE}"))
        db.commit()
    except Exception:
        db.rollback()

    if not create_fts5_table(db):
        return 0

    return populate_fts5_index(db)


def search_fts5(
    db: Session,
    query: str,
    max_results: int = 30,
) -> list[dict]:
    """
    Search knowledge_chunks via FTS5 with BM25 ranking.
    Returns list of {"rowid": int, "bm25_score": float} dicts.
    Higher (less negative) bm25 scores = better matches.
    """
    # Sanitize query for FTS5: remove special chars, keep words
    import re
    words = re.findall(r'\w+', query.lower())
    if not words:
        return []

    # Build FTS5 query: OR between words for broad matching
    fts_query = " OR ".join(words[:8])

    try:
        result = db.execute(text(f"""
            SELECT rowid, bm25({FTS_TABLE}) as score
            FROM {FTS_TABLE}
            WHERE {FTS_TABLE} MATCH :query
            ORDER BY score
            LIMIT :limit
        """), {"query": fts_query, "limit": max_results})

        return [{"rowid": row[0], "bm25_score": row[1]} for row in result.fetchall()]
    except Exception as e:
        logger.warning(f"FTS5 search failed (falling back to LIKE): {e}")
        return []


def ensure_fts5(db: Session):
    """Ensure FTS5 table exists, create and populate if not."""
    if not is_fts5_available(db):
        logger.info("FTS5 table not found, creating...")
        if create_fts5_table(db):
            populate_fts5_index(db)

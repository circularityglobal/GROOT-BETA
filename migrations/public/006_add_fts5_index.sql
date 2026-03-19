-- Migration 006: Add FTS5 full-text search index for knowledge_chunks
-- Provides BM25-ranked search, replacing O(n) LIKE queries.
-- FTS5 is built into SQLite — no external dependencies.

-- Create FTS5 virtual table (external content mode — mirrors knowledge_chunks.content)
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks_fts
USING fts5(content, content='knowledge_chunks', content_rowid='rowid');

-- Sync triggers: keep FTS5 index up to date with knowledge_chunks mutations

CREATE TRIGGER IF NOT EXISTS knowledge_chunks_ai AFTER INSERT ON knowledge_chunks
BEGIN
    INSERT INTO knowledge_chunks_fts(rowid, content)
    VALUES (new.rowid, new.content);
END;

CREATE TRIGGER IF NOT EXISTS knowledge_chunks_ad AFTER DELETE ON knowledge_chunks
BEGIN
    INSERT INTO knowledge_chunks_fts(knowledge_chunks_fts, rowid, content)
    VALUES ('delete', old.rowid, old.content);
END;

CREATE TRIGGER IF NOT EXISTS knowledge_chunks_au AFTER UPDATE ON knowledge_chunks
BEGIN
    INSERT INTO knowledge_chunks_fts(knowledge_chunks_fts, rowid, content)
    VALUES ('delete', old.rowid, old.content);
    INSERT INTO knowledge_chunks_fts(rowid, content)
    VALUES (new.rowid, new.content);
END;

-- Populate FTS5 index from existing chunks
INSERT INTO knowledge_chunks_fts(rowid, content)
SELECT rowid, content FROM knowledge_chunks;

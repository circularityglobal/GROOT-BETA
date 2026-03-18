-- Migration 005: Add document sharing table for collaboration
-- Enables users to share private documents with other users.

CREATE TABLE IF NOT EXISTS document_shares (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    shared_with_id TEXT NOT NULL,
    permission TEXT DEFAULT 'read',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_document_shares_document_id ON document_shares(document_id);
CREATE INDEX IF NOT EXISTS idx_document_shares_shared_with ON document_shares(shared_with_id);

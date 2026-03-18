-- Migration 004: Add user ownership and visibility to knowledge documents
-- Enables private/public document layers for NotebookLM-like experience.
-- Existing docs default to 'platform' (globally visible, admin-managed).

ALTER TABLE knowledge_documents ADD COLUMN user_id TEXT;
ALTER TABLE knowledge_documents ADD COLUMN visibility TEXT DEFAULT 'platform';

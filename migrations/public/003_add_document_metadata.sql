-- Migration 003: Add document metadata columns for sovereign document ingestion
-- Adds auto-tagging, file type tracking, and rich metadata to knowledge_documents.
-- All columns nullable — existing rows get NULL, no data migration needed.

ALTER TABLE knowledge_documents ADD COLUMN tags TEXT;           -- JSON array of auto-generated semantic tags
ALTER TABLE knowledge_documents ADD COLUMN doc_type TEXT;       -- pdf|docx|xlsx|csv|txt|md|json|sol
ALTER TABLE knowledge_documents ADD COLUMN page_count INTEGER;  -- page count (PDF) or sheet count (XLSX)
ALTER TABLE knowledge_documents ADD COLUMN metadata_json TEXT;  -- JSON: {author, created, file_size, ...}

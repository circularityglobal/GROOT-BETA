-- Add embedding column to knowledge_chunks for semantic RAG
-- JSON-serialized float array (384-dim from all-MiniLM-L6-v2)
ALTER TABLE knowledge_chunks ADD COLUMN embedding TEXT;

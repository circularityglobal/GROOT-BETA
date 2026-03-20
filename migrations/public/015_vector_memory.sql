-- Migration 015: Vector Memory System
-- Hybrid vector search with sqlite-vec, embedding caching, memory decay.
-- The vec_memories virtual table is created at runtime (requires extension loaded).

CREATE TABLE IF NOT EXISTS vector_memories (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES agent_registrations(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    metadata_json TEXT,
    importance REAL DEFAULT 0.5,
    embedding_json TEXT,
    access_count INTEGER DEFAULT 0,
    last_accessed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_vm_agent_id ON vector_memories(agent_id);
CREATE INDEX IF NOT EXISTS idx_vm_type ON vector_memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_vm_importance ON vector_memories(importance);
CREATE INDEX IF NOT EXISTS idx_vm_created ON vector_memories(created_at);

CREATE TABLE IF NOT EXISTS vector_interactions (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES agent_registrations(id) ON DELETE CASCADE,
    input_text TEXT NOT NULL,
    output_text TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_vi_agent_id ON vector_interactions(agent_id);

CREATE TABLE IF NOT EXISTS vector_memory_links (
    id TEXT PRIMARY KEY,
    memory_id TEXT NOT NULL REFERENCES vector_memories(id) ON DELETE CASCADE,
    interaction_id TEXT NOT NULL REFERENCES vector_interactions(id) ON DELETE CASCADE,
    relevance_score REAL DEFAULT 1.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_vml_memory ON vector_memory_links(memory_id);
CREATE INDEX IF NOT EXISTS idx_vml_interaction ON vector_memory_links(interaction_id);

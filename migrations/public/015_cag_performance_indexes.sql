-- Migration 015: CAG performance indexes
-- Critical for contract search at 1000+ contracts scale.
-- Without these, LIKE queries scan every row.

-- ── ContractRepo search indexes ─────────────────────────────
CREATE INDEX IF NOT EXISTS idx_cr_name ON contract_repos(name);
CREATE INDEX IF NOT EXISTS idx_cr_chain_public ON contract_repos(chain, is_public, is_active);
CREATE INDEX IF NOT EXISTS idx_cr_slug_unique ON contract_repos(slug);

-- ── ContractFunction search indexes ─────────────────────────
CREATE INDEX IF NOT EXISTS idx_cf_function_name ON contract_functions(function_name);
CREATE INDEX IF NOT EXISTS idx_cf_signature ON contract_functions(signature);
CREATE INDEX IF NOT EXISTS idx_cf_contract_enabled ON contract_functions(contract_id, is_sdk_enabled);
CREATE INDEX IF NOT EXISTS idx_cf_access_level ON contract_functions(access_level);

-- ── SDKDefinition lookup indexes ────────────────────────────
-- idx_sd_public, idx_sd_address, idx_sd_contract already in 014

-- ── KnowledgeDocument indexes ───────────────────────────────
CREATE INDEX IF NOT EXISTS idx_kd_visibility ON knowledge_documents(visibility);
CREATE INDEX IF NOT EXISTS idx_kd_category ON knowledge_documents(category);
CREATE INDEX IF NOT EXISTS idx_kd_user_id ON knowledge_documents(user_id);

-- ── KnowledgeChunk indexes ──────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_kc_document_id ON knowledge_chunks(document_id);

-- ── PendingAction indexes ───────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_pa_status ON pending_actions(status);
CREATE INDEX IF NOT EXISTS idx_pa_action_type ON pending_actions(action_type);

-- ── DeploymentRecord indexes ────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_dr_user_id ON deployment_records(user_id);
CREATE INDEX IF NOT EXISTS idx_dr_deployer ON deployment_records(deployer_address);
CREATE INDEX IF NOT EXISTS idx_dr_chain ON deployment_records(chain);

-- ── FTS5 for contract search (if supported) ─────────────────
-- Creates a full-text search index over contract names, descriptions, and tags.
-- This replaces slow LIKE queries with fast BM25-ranked search.
CREATE VIRTUAL TABLE IF NOT EXISTS contract_repos_fts USING fts5(
    name, description, tags,
    content='contract_repos',
    content_rowid='rowid'
);

-- Auto-sync FTS with contract_repos table
CREATE TRIGGER IF NOT EXISTS contract_repos_fts_insert AFTER INSERT ON contract_repos BEGIN
    INSERT INTO contract_repos_fts(rowid, name, description, tags)
    VALUES (new.rowid, new.name, new.description, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS contract_repos_fts_delete AFTER DELETE ON contract_repos BEGIN
    INSERT INTO contract_repos_fts(contract_repos_fts, rowid, name, description, tags)
    VALUES ('delete', old.rowid, old.name, old.description, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS contract_repos_fts_update AFTER UPDATE ON contract_repos BEGIN
    INSERT INTO contract_repos_fts(contract_repos_fts, rowid, name, description, tags)
    VALUES ('delete', old.rowid, old.name, old.description, old.tags);
    INSERT INTO contract_repos_fts(rowid, name, description, tags)
    VALUES (new.rowid, new.name, new.description, new.tags);
END;

-- ── FTS5 for contract functions ─────────────────────────────
CREATE VIRTUAL TABLE IF NOT EXISTS contract_functions_fts USING fts5(
    function_name, signature,
    content='contract_functions',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS contract_functions_fts_insert AFTER INSERT ON contract_functions BEGIN
    INSERT INTO contract_functions_fts(rowid, function_name, signature)
    VALUES (new.rowid, new.function_name, new.signature);
END;

CREATE TRIGGER IF NOT EXISTS contract_functions_fts_delete AFTER DELETE ON contract_functions BEGIN
    INSERT INTO contract_functions_fts(contract_functions_fts, rowid, function_name, signature)
    VALUES ('delete', old.rowid, old.function_name, old.signature);
END;

CREATE TRIGGER IF NOT EXISTS contract_functions_fts_update AFTER UPDATE ON contract_functions BEGIN
    INSERT INTO contract_functions_fts(contract_functions_fts, rowid, function_name, signature)
    VALUES ('delete', old.rowid, old.function_name, old.signature);
    INSERT INTO contract_functions_fts(rowid, function_name, signature)
    VALUES (new.rowid, new.function_name, new.signature);
END;

"""Shared fixtures for skills tests."""

import os
import sqlite3
import uuid

import pytest


def _uuid():
    return str(uuid.uuid4())


# ── Schema creation (matches actual SQLAlchemy models) ────────────────────

_KNOWLEDGE_SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'docs',
    source_filename TEXT,
    content TEXT NOT NULL DEFAULT '',
    content_hash TEXT NOT NULL,
    chunk_count INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    uploaded_by TEXT NOT NULL DEFAULT 'admin',
    user_id TEXT,
    visibility TEXT DEFAULT 'platform',
    tags TEXT,
    doc_type TEXT,
    page_count INTEGER,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    token_count INTEGER DEFAULT 0,
    embedding TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contract_definitions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    chain TEXT NOT NULL,
    address TEXT,
    abi_json TEXT,
    description TEXT NOT NULL DEFAULT '',
    logic_summary TEXT,
    category TEXT DEFAULT 'defi',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_REGISTRY_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS registry_projects (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    visibility TEXT DEFAULT 'public',
    category TEXT DEFAULT 'utility',
    chain TEXT DEFAULT 'ethereum',
    stars_count INTEGER DEFAULT 0,
    forks_count INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS registry_abis (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES registry_projects(id),
    contract_name TEXT NOT NULL,
    contract_address TEXT,
    chain TEXT NOT NULL,
    abi_json TEXT NOT NULL,
    compiler_version TEXT,
    optimization_enabled INTEGER DEFAULT 0,
    source_hash TEXT,
    bytecode_hash TEXT,
    is_verified INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contract_security_flags (
    id TEXT PRIMARY KEY,
    abi_id TEXT NOT NULL REFERENCES registry_abis(id) ON DELETE CASCADE,
    pattern TEXT NOT NULL,
    severity TEXT NOT NULL,
    location TEXT,
    description TEXT,
    risk TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS registry_stars (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    project_id TEXT NOT NULL REFERENCES registry_projects(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, project_id)
);

CREATE TABLE IF NOT EXISTS registry_forks (
    id TEXT PRIMARY KEY,
    source_project_id TEXT NOT NULL REFERENCES registry_projects(id),
    forked_project_id TEXT NOT NULL REFERENCES registry_projects(id),
    forked_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_project_id, forked_by)
);
"""

_CHAIN_SCHEMA = """
CREATE TABLE IF NOT EXISTS chain_watchers (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    chain TEXT NOT NULL,
    contract_address TEXT NOT NULL,
    event_names TEXT,
    rpc_url TEXT,
    from_block INTEGER DEFAULT 0,
    last_processed_block INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    polling_interval_seconds INTEGER DEFAULT 30,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chain_events (
    id TEXT PRIMARY KEY,
    watcher_id TEXT NOT NULL REFERENCES chain_watchers(id) ON DELETE CASCADE,
    chain TEXT NOT NULL,
    contract_address TEXT NOT NULL,
    event_name TEXT,
    block_number INTEGER NOT NULL,
    tx_hash TEXT NOT NULL,
    log_index INTEGER NOT NULL,
    decoded_data TEXT,
    raw_data TEXT,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    """Create temp SQLite with full schema matching real models."""
    db_file = tmp_path / "test_public.db"
    conn = sqlite3.connect(str(db_file))
    conn.executescript(_KNOWLEDGE_SCHEMA)
    conn.executescript(_REGISTRY_SCHEMA)
    conn.executescript(_CHAIN_SCHEMA)
    conn.commit()
    return str(db_file), conn


@pytest.fixture
def knowledge_db(tmp_db):
    """Temp DB seeded with knowledge data (3 docs, 9 chunks, 8 embeddings)."""
    db_path, conn = tmp_db

    # 3 documents
    for i in range(3):
        doc_id = f"doc-{i}"
        conn.execute(
            "INSERT INTO knowledge_documents (id, title, category, content_hash, content, uploaded_by, doc_type) "
            "VALUES (?, ?, 'docs', ?, 'content', 'admin', 'txt')",
            (doc_id, f"Doc {i}", f"hash-{i}")
        )
        # 3 chunks each
        for j in range(3):
            chunk_id = f"chunk-{i}-{j}"
            # All chunks get embeddings except the last chunk of the last doc
            embedding = '[0.1, 0.2, 0.3]' if not (i == 2 and j == 2) else None
            conn.execute(
                "INSERT INTO knowledge_chunks (id, document_id, chunk_index, content, embedding) "
                "VALUES (?, ?, ?, 'chunk text', ?)",
                (chunk_id, doc_id, j, embedding)
            )

    conn.commit()
    return db_path, conn


@pytest.fixture
def contract_db(tmp_db):
    """Temp DB seeded with registry + chain data for contract-watcher tests."""
    db_path, conn = tmp_db

    # User
    conn.execute("INSERT INTO users (id) VALUES ('user-1')")

    # Project
    proj_id = "proj-1"
    conn.execute(
        "INSERT INTO registry_projects (id, owner_id, slug, name) VALUES (?, 'user-1', 'test/project', 'Test Project')",
        (proj_id,)
    )

    # Clean ABI
    clean_abi = '[{"type":"function","name":"transfer","inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"outputs":[{"name":"","type":"bool"}]}]'
    conn.execute(
        "INSERT INTO registry_abis (id, project_id, contract_name, chain, abi_json) VALUES (?, ?, 'ERC20Token', 'ethereum', ?)",
        ("abi-clean", proj_id, clean_abi)
    )

    # Dangerous ABI (selfdestruct + transferOwnership)
    dangerous_abi = '[{"type":"function","name":"selfdestruct","inputs":[],"outputs":[]},{"type":"function","name":"transferOwnership","inputs":[{"name":"newOwner","type":"address"}],"outputs":[]}]'
    conn.execute(
        "INSERT INTO registry_abis (id, project_id, contract_name, chain, abi_json) VALUES (?, ?, 'DangerContract', 'ethereum', ?)",
        ("abi-danger", proj_id, dangerous_abi)
    )

    # Chain watcher
    watcher_id = "watcher-1"
    conn.execute(
        "INSERT INTO chain_watchers (id, user_id, chain, contract_address, is_active) VALUES (?, 'user-1', 'ethereum', '0xabc', 1)",
        (watcher_id,)
    )

    # Chain events
    for i in range(5):
        conn.execute(
            "INSERT INTO chain_events (id, watcher_id, chain, contract_address, block_number, tx_hash, log_index) "
            "VALUES (?, ?, 'ethereum', '0xabc', ?, ?, 0)",
            (f"evt-{i}", watcher_id, 1000 + i, f"0xtx{i}")
        )

    # Star
    conn.execute(
        "INSERT INTO registry_stars (id, user_id, project_id) VALUES (?, 'user-1', ?)",
        (_uuid(), proj_id)
    )

    conn.commit()
    return db_path, conn


@pytest.fixture
def env_patch(monkeypatch, tmp_db):
    """Patch env vars for skill scripts."""
    db_path, _ = tmp_db
    monkeypatch.setenv("DATABASE_PATH", db_path)
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_PORT", raising=False)
    return db_path


# ── Sample ABIs ───────────────────────────────────────────────────────────

CLEAN_ABI = [
    {"type": "function", "name": "transfer", "inputs": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}], "outputs": [{"name": "", "type": "bool"}]},
    {"type": "function", "name": "balanceOf", "inputs": [{"name": "account", "type": "address"}], "outputs": [{"name": "", "type": "uint256"}]},
    {"type": "event", "name": "Transfer", "inputs": [{"name": "from", "type": "address", "indexed": True}, {"name": "to", "type": "address", "indexed": True}, {"name": "value", "type": "uint256"}]},
]

DANGEROUS_ABI = [
    {"type": "function", "name": "selfdestruct", "inputs": [], "outputs": []},
    {"type": "function", "name": "delegatecall", "inputs": [{"name": "target", "type": "address"}], "outputs": []},
    {"type": "function", "name": "transferOwnership", "inputs": [{"name": "newOwner", "type": "address"}], "outputs": []},
    {"type": "function", "name": "upgradeTo", "inputs": [{"name": "impl", "type": "address"}], "outputs": []},
]

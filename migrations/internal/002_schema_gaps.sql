-- Migration 002: Internal DB schema gap fixes
-- Ensures all internal tables exist for databases created via migrations only.
-- Safe to run on databases already using create_all().

-- ── Core internal tables (model exists, no explicit migration) ──

CREATE TABLE IF NOT EXISTS server_secrets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    encrypted_value TEXT NOT NULL,
    description TEXT,
    created_by TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    rotated_at DATETIME
);
CREATE INDEX IF NOT EXISTS idx_ss_name ON server_secrets(name);

CREATE TABLE IF NOT EXISTS role_assignments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    granted_by TEXT NOT NULL,
    granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    revoked_at DATETIME,
    is_active INTEGER DEFAULT 1,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_ra_user ON role_assignments(user_id);

CREATE TABLE IF NOT EXISTS admin_audit_log (
    id TEXT PRIMARY KEY,
    admin_username TEXT NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT,
    details TEXT,
    ip_address TEXT,
    user_agent TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS product_registry (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    build_key_hash TEXT NOT NULL,
    current_version TEXT,
    connection_count INTEGER DEFAULT 0,
    last_connected_at DATETIME,
    registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS mcp_server_registry (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    url TEXT NOT NULL,
    transport TEXT NOT NULL,
    auth_type TEXT DEFAULT 'none',
    auth_value TEXT,
    capabilities TEXT,
    status TEXT DEFAULT 'active',
    registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_health_check_at DATETIME,
    is_healthy INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_msr_name ON mcp_server_registry(name);

CREATE TABLE IF NOT EXISTS system_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    data_type TEXT DEFAULT 'string',
    description TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT
);

CREATE TABLE IF NOT EXISTS health_check_logs (
    id TEXT PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    inference_ok INTEGER NOT NULL,
    inference_latency_ms INTEGER,
    database_ok INTEGER NOT NULL,
    smtp_ok INTEGER,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS custodial_wallets (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,
    eth_address TEXT NOT NULL UNIQUE,
    eth_address_hash TEXT NOT NULL,
    share_count INTEGER NOT NULL DEFAULT 5,
    threshold INTEGER NOT NULL DEFAULT 3,
    chain_id INTEGER NOT NULL DEFAULT 1,
    encryption_salt TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_signing_at DATETIME
);
CREATE INDEX IF NOT EXISTS idx_cw_user ON custodial_wallets(user_id);
CREATE INDEX IF NOT EXISTS idx_cw_address ON custodial_wallets(eth_address);

CREATE TABLE IF NOT EXISTS wallet_shares (
    id TEXT PRIMARY KEY,
    wallet_id TEXT NOT NULL REFERENCES custodial_wallets(id),
    share_index INTEGER NOT NULL,
    encrypted_share TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ws_wallet ON wallet_shares(wallet_id);

CREATE TABLE IF NOT EXISTS sandbox_environments (
    id TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL,
    status TEXT DEFAULT 'provisioning',
    container_id TEXT,
    container_name TEXT,
    image_tag TEXT,
    port INTEGER,
    access_url TEXT,
    network_isolated INTEGER DEFAULT 1,
    resource_limits TEXT,
    logs TEXT,
    created_by TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    destroyed_at DATETIME
);
CREATE INDEX IF NOT EXISTS idx_se_submission ON sandbox_environments(submission_id);

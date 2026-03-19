-- Migration 008: Add Chain Watchers, Messenger Links, DApp Builds

CREATE TABLE IF NOT EXISTS chain_watchers (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    chain TEXT NOT NULL,
    contract_address TEXT NOT NULL,
    event_names TEXT,
    rpc_url TEXT,
    from_block INTEGER DEFAULT 0,
    last_processed_block INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    polling_interval_seconds INTEGER DEFAULT 30,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cw_user_id ON chain_watchers(user_id);

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
    received_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ce_watcher_id ON chain_events(watcher_id);

CREATE TABLE IF NOT EXISTS messenger_links (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    platform TEXT NOT NULL,
    platform_user_id TEXT NOT NULL,
    platform_username TEXT,
    is_verified INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ml_user_id ON messenger_links(user_id);
CREATE INDEX IF NOT EXISTS idx_ml_platform_user ON messenger_links(platform_user_id);

CREATE TABLE IF NOT EXISTS dapp_builds (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    project_id TEXT,
    template_name TEXT NOT NULL,
    config_json TEXT,
    status TEXT DEFAULT 'building',
    output_filename TEXT,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);
CREATE INDEX IF NOT EXISTS idx_db_user_id ON dapp_builds(user_id);

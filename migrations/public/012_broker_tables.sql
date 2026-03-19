-- Broker system tables
-- Migration 012: broker_sessions, broker_fee_configs

CREATE TABLE IF NOT EXISTS broker_sessions (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES users(id),
    provider_id TEXT REFERENCES users(id),
    service_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'requested',
    config_json TEXT,
    result_json TEXT,
    payment_record_id TEXT REFERENCES payment_records(id),
    conversation_id TEXT REFERENCES conversations(id),
    pipeline_run_id TEXT REFERENCES pipeline_runs(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME
);
CREATE INDEX IF NOT EXISTS idx_broker_sessions_client ON broker_sessions(client_id);
CREATE INDEX IF NOT EXISTS idx_broker_sessions_status ON broker_sessions(status);

CREATE TABLE IF NOT EXISTS broker_fee_configs (
    id TEXT PRIMARY KEY,
    service_type TEXT NOT NULL UNIQUE,
    base_fee_usd REAL DEFAULT 0.0,
    percentage_fee REAL DEFAULT 5.0,
    token_options TEXT,
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_broker_fee_configs_service ON broker_fee_configs(service_type);

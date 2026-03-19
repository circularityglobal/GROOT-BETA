-- Payment & Revenue System tables
-- Migration 011: fee_schedules, payment_records, subscriptions, revenue_splits

CREATE TABLE IF NOT EXISTS fee_schedules (
    id TEXT PRIMARY KEY,
    service_type TEXT NOT NULL,
    fee_percentage REAL DEFAULT 0.0,
    flat_fee_usd REAL DEFAULT 0.0,
    tokens_accepted TEXT,
    tier_overrides TEXT,
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_fee_schedules_service ON fee_schedules(service_type);

CREATE TABLE IF NOT EXISTS payment_records (
    id TEXT PRIMARY KEY,
    payer_id TEXT NOT NULL REFERENCES users(id),
    recipient_id TEXT REFERENCES users(id),
    payment_type TEXT NOT NULL,
    amount_usd REAL NOT NULL,
    token_symbol TEXT,
    token_amount REAL,
    tx_hash TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    reference_type TEXT,
    reference_id TEXT,
    fee_schedule_id TEXT REFERENCES fee_schedules(id),
    platform_fee_usd REAL DEFAULT 0.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);
CREATE INDEX IF NOT EXISTS idx_payment_records_payer ON payment_records(payer_id);
CREATE INDEX IF NOT EXISTS idx_payment_records_status ON payment_records(status);
CREATE INDEX IF NOT EXISTS idx_payment_records_tx_hash ON payment_records(tx_hash);

CREATE TABLE IF NOT EXISTS subscriptions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    app_id TEXT REFERENCES app_listings(id),
    plan_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    current_period_start DATETIME,
    current_period_end DATETIME,
    payment_record_id TEXT REFERENCES payment_records(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    cancelled_at DATETIME
);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_plan_type ON subscriptions(plan_type);

CREATE TABLE IF NOT EXISTS revenue_splits (
    id TEXT PRIMARY KEY,
    app_id TEXT REFERENCES app_listings(id),
    split_type TEXT NOT NULL,
    platform_pct REAL DEFAULT 50.0,
    developer_pct REAL DEFAULT 50.0,
    broker_pct REAL DEFAULT 0.0,
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

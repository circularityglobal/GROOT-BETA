-- Migration 001: Add Scheduler and Script Execution tables to internal.db

CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    task_type TEXT NOT NULL,
    schedule TEXT NOT NULL,
    handler_path TEXT NOT NULL,
    handler_args TEXT,
    is_enabled INTEGER DEFAULT 1,
    last_run_at DATETIME,
    next_run_at DATETIME,
    last_result TEXT,
    last_error TEXT,
    run_count INTEGER DEFAULT 0,
    created_by TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_st_name ON scheduled_tasks(name);

CREATE TABLE IF NOT EXISTS script_executions (
    id TEXT PRIMARY KEY,
    script_name TEXT NOT NULL,
    args_json TEXT,
    status TEXT DEFAULT 'pending',
    output TEXT,
    error TEXT,
    started_by TEXT,
    started_at DATETIME,
    completed_at DATETIME,
    duration_ms INTEGER
);
CREATE INDEX IF NOT EXISTS idx_se_script_name ON script_executions(script_name);

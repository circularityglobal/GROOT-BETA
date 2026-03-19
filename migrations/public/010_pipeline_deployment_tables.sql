-- Pipeline execution DAG tables + deployment tracking
-- Migration 010: pipeline_runs, pipeline_steps, pending_actions, deployment_records

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    agent_task_id TEXT REFERENCES agent_tasks(id),
    pipeline_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    dag_json TEXT,
    current_step TEXT,
    config_json TEXT,
    result_json TEXT,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME
);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_user ON pipeline_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status);

CREATE TABLE IF NOT EXISTS pipeline_steps (
    id TEXT PRIMARY KEY,
    pipeline_id TEXT NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    step_name TEXT NOT NULL,
    step_index INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    worker_type TEXT NOT NULL,
    input_json TEXT,
    output_json TEXT,
    error_message TEXT,
    depends_on TEXT,
    started_at DATETIME,
    completed_at DATETIME
);
CREATE INDEX IF NOT EXISTS idx_pipeline_steps_pipeline ON pipeline_steps(pipeline_id);

CREATE TABLE IF NOT EXISTS pending_actions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    action_type TEXT NOT NULL,
    target_chain TEXT,
    target_address TEXT,
    payload_json TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    reviewer_id TEXT REFERENCES users(id),
    review_note TEXT,
    pipeline_step_id TEXT REFERENCES pipeline_steps(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    reviewed_at DATETIME,
    expires_at DATETIME
);
CREATE INDEX IF NOT EXISTS idx_pending_actions_user ON pending_actions(user_id);
CREATE INDEX IF NOT EXISTS idx_pending_actions_status ON pending_actions(status);

CREATE TABLE IF NOT EXISTS deployment_records (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    pipeline_run_id TEXT REFERENCES pipeline_runs(id),
    contract_address TEXT NOT NULL,
    chain TEXT NOT NULL,
    chain_id INTEGER,
    deployer_address TEXT,
    owner_address TEXT,
    tx_hash TEXT,
    block_number INTEGER,
    constructor_args_json TEXT,
    abi_hash TEXT,
    ownership_status TEXT NOT NULL DEFAULT 'groot_owned',
    transfer_tx_hash TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    transferred_at DATETIME
);
CREATE INDEX IF NOT EXISTS idx_deployment_records_user ON deployment_records(user_id);
CREATE INDEX IF NOT EXISTS idx_deployment_records_contract ON deployment_records(contract_address);

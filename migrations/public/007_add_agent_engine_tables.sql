-- Migration 007: Add Agent Engine tables
-- SOUL identity, 4-tier memory, task tracking, delegation

CREATE TABLE IF NOT EXISTS agent_souls (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL UNIQUE REFERENCES agent_registrations(id) ON DELETE CASCADE,
    soul_md TEXT NOT NULL,
    persona TEXT,
    goals TEXT,
    constraints TEXT,
    tools_allowed TEXT,
    delegation_policy TEXT DEFAULT 'none',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_agent_souls_agent_id ON agent_souls(agent_id);

CREATE TABLE IF NOT EXISTS agent_memory_working (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES agent_registrations(id) ON DELETE CASCADE,
    task_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME
);
CREATE INDEX IF NOT EXISTS idx_amw_agent_id ON agent_memory_working(agent_id);
CREATE INDEX IF NOT EXISTS idx_amw_task_id ON agent_memory_working(task_id);

CREATE TABLE IF NOT EXISTS agent_memory_episodic (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES agent_registrations(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    context_json TEXT,
    outcome TEXT NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ame_agent_id ON agent_memory_episodic(agent_id);

CREATE TABLE IF NOT EXISTS agent_memory_semantic (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES agent_registrations(id) ON DELETE CASCADE,
    fact TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    source TEXT,
    embedding TEXT,
    usage_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ams_agent_id ON agent_memory_semantic(agent_id);

CREATE TABLE IF NOT EXISTS agent_memory_procedural (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES agent_registrations(id) ON DELETE CASCADE,
    pattern_name TEXT NOT NULL,
    trigger_condition TEXT NOT NULL,
    action_sequence TEXT NOT NULL,
    success_rate REAL DEFAULT 0.0,
    usage_count INTEGER DEFAULT 0,
    last_used_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_amp_agent_id ON agent_memory_procedural(agent_id);

CREATE TABLE IF NOT EXISTS agent_tasks (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES agent_registrations(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id),
    description TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    current_phase TEXT,
    plan_json TEXT,
    steps_json TEXT,
    result_json TEXT,
    error_message TEXT,
    tokens_used INTEGER DEFAULT 0,
    inference_calls INTEGER DEFAULT 0,
    tool_calls INTEGER DEFAULT 0,
    started_at DATETIME,
    completed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_at_agent_id ON agent_tasks(agent_id);
CREATE INDEX IF NOT EXISTS idx_at_user_id ON agent_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_at_status ON agent_tasks(status);

CREATE TABLE IF NOT EXISTS agent_delegations (
    id TEXT PRIMARY KEY,
    source_agent_id TEXT NOT NULL REFERENCES agent_registrations(id),
    target_agent_id TEXT NOT NULL REFERENCES agent_registrations(id),
    source_task_id TEXT NOT NULL REFERENCES agent_tasks(id),
    delegated_task_id TEXT REFERENCES agent_tasks(id),
    subtask_description TEXT NOT NULL,
    status TEXT DEFAULT 'requested',
    result_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME
);
CREATE INDEX IF NOT EXISTS idx_ad_source ON agent_delegations(source_agent_id);
CREATE INDEX IF NOT EXISTS idx_ad_target ON agent_delegations(target_agent_id);

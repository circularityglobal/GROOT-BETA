-- Infrastructure node registry — Oracle Cloud instances and other servers
-- Admin manages these to scale the platform across multiple instances

CREATE TABLE IF NOT EXISTS infra_nodes (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    provider TEXT NOT NULL DEFAULT 'oracle_cloud',
    region TEXT,
    instance_type TEXT,
    instance_id TEXT UNIQUE,
    compartment_id TEXT,
    public_ip TEXT,
    private_ip TEXT,
    ssh_port INTEGER DEFAULT 22,
    cpu_count INTEGER,
    memory_gb INTEGER,
    disk_gb INTEGER,
    role TEXT NOT NULL DEFAULT 'worker',
    services TEXT,
    status TEXT DEFAULT 'provisioning',
    api_endpoint TEXT,
    last_health_check DATETIME,
    last_health_status TEXT,
    health_check_latency_ms INTEGER,
    notes TEXT,
    added_by TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_infra_nodes_name ON infra_nodes(name);
CREATE INDEX IF NOT EXISTS idx_infra_nodes_status ON infra_nodes(status);

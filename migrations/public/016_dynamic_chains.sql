-- Migration 016: Dynamic chain registry + multi-chain contract deployments
-- Replaces 7+ hardcoded chain dicts with a single database table.

CREATE TABLE IF NOT EXISTS supported_chains (
    chain_id        INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    short_name      TEXT NOT NULL UNIQUE,
    currency        TEXT DEFAULT 'ETH',
    rpc_url         TEXT NOT NULL,
    explorer_url    TEXT,
    explorer_api_url TEXT,
    icon_url        TEXT,
    is_testnet      INTEGER DEFAULT 0,
    is_active       INTEGER DEFAULT 1,
    added_by        TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sc_short_name ON supported_chains(short_name);
CREATE INDEX IF NOT EXISTS idx_sc_active ON supported_chains(is_active);

CREATE TABLE IF NOT EXISTS contract_deployments (
    id              TEXT PRIMARY KEY,
    contract_id     TEXT NOT NULL REFERENCES contract_repos(id) ON DELETE CASCADE,
    chain_id        INTEGER NOT NULL REFERENCES supported_chains(chain_id),
    address         TEXT NOT NULL,
    is_verified     INTEGER DEFAULT 0,
    deployed_at     DATETIME,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chain_id, address)
);
CREATE INDEX IF NOT EXISTS idx_cd_contract ON contract_deployments(contract_id);
CREATE INDEX IF NOT EXISTS idx_cd_chain ON contract_deployments(chain_id);
CREATE INDEX IF NOT EXISTS idx_cd_address ON contract_deployments(address);

-- Seed the 6 core chains
INSERT OR IGNORE INTO supported_chains (chain_id, name, short_name, currency, rpc_url, explorer_url, explorer_api_url, is_testnet, added_by) VALUES
    (1,        'Ethereum Mainnet', 'ethereum', 'ETH',   'https://eth.llamarpc.com',       'https://etherscan.io',                'https://api.etherscan.io/api',               0, 'system'),
    (137,      'Polygon',          'polygon',  'MATIC', 'https://polygon-rpc.com',         'https://polygonscan.com',             'https://api.polygonscan.com/api',             0, 'system'),
    (42161,    'Arbitrum One',     'arbitrum',  'ETH',  'https://arb1.arbitrum.io/rpc',    'https://arbiscan.io',                 'https://api.arbiscan.io/api',                0, 'system'),
    (10,       'Optimism',         'optimism',  'ETH',  'https://mainnet.optimism.io',     'https://optimistic.etherscan.io',     'https://api-optimistic.etherscan.io/api',    0, 'system'),
    (8453,     'Base',             'base',      'ETH',  'https://mainnet.base.org',        'https://basescan.org',                'https://api.basescan.org/api',               0, 'system'),
    (11155111, 'Sepolia',          'sepolia',   'ETH',  'https://rpc.sepolia.org',         'https://sepolia.etherscan.io',        'https://api-sepolia.etherscan.io/api',       1, 'system');

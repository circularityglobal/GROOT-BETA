-- Migration 014: Wizard system + schema gap fixes
-- Adds missing columns to app_listings and ensures all tables exist.
-- Safe to run on both fresh databases (create_all) and existing databases.

-- ── AppListing missing columns (model defines but 009 migration omits) ──
-- These are idempotent: SQLite ignores ALTER TABLE ADD COLUMN if column exists
-- via create_all(), and adds it if running on a database created via migrations only.

-- Pricing columns
ALTER TABLE app_listings ADD COLUMN price_type TEXT DEFAULT 'free';
ALTER TABLE app_listings ADD COLUMN price_amount REAL DEFAULT 0.0;
ALTER TABLE app_listings ADD COLUMN price_token TEXT;
ALTER TABLE app_listings ADD COLUMN price_token_amount REAL;

-- Delivery columns
ALTER TABLE app_listings ADD COLUMN license_type TEXT DEFAULT 'open';
ALTER TABLE app_listings ADD COLUMN download_url TEXT;
ALTER TABLE app_listings ADD COLUMN external_url TEXT;
ALTER TABLE app_listings ADD COLUMN download_count INTEGER DEFAULT 0;

-- Admin flag
ALTER TABLE app_listings ADD COLUMN listed_by_admin INTEGER DEFAULT 0;

-- ── App Submission tables (model exists, no migration) ──
CREATE TABLE IF NOT EXISTS app_submissions (
    id TEXT PRIMARY KEY,
    app_id TEXT NOT NULL REFERENCES app_listings(id) ON DELETE CASCADE,
    submitter_id TEXT NOT NULL REFERENCES users(id),
    status TEXT DEFAULT 'draft',
    version TEXT DEFAULT '1.0.0',
    artifact_type TEXT DEFAULT 'zip',
    artifact_url TEXT,
    artifact_hash TEXT,
    build_logs TEXT,
    review_notes TEXT,
    reviewer_id TEXT REFERENCES users(id),
    sandbox_id TEXT,
    submitted_at DATETIME,
    reviewed_at DATETIME,
    published_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_as_app_id ON app_submissions(app_id);
CREATE INDEX IF NOT EXISTS idx_as_status ON app_submissions(status);

CREATE TABLE IF NOT EXISTS submission_notes (
    id TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL REFERENCES app_submissions(id) ON DELETE CASCADE,
    author_id TEXT NOT NULL REFERENCES users(id),
    note TEXT NOT NULL,
    note_type TEXT DEFAULT 'comment',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sn_submission ON submission_notes(submission_id);

-- ── Wallet identity tables (model exists, no migration) ──
CREATE TABLE IF NOT EXISTS wallet_identities (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    chain TEXT NOT NULL,
    wallet_address TEXT NOT NULL,
    display_name TEXT,
    ens_name TEXT,
    ens_avatar TEXT,
    pseudo_ipv6 TEXT,
    is_primary INTEGER DEFAULT 0,
    verified_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_wi_user ON wallet_identities(user_id);
CREATE INDEX IF NOT EXISTS idx_wi_address ON wallet_identities(wallet_address);
CREATE UNIQUE INDEX IF NOT EXISTS idx_wi_chain_addr ON wallet_identities(chain, wallet_address);

CREATE TABLE IF NOT EXISTS wallet_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    chain TEXT NOT NULL,
    wallet_address TEXT NOT NULL,
    session_token TEXT NOT NULL UNIQUE,
    expires_at DATETIME NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ws_user ON wallet_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_ws_token ON wallet_sessions(session_token);

-- ── Messaging tables (model exists, no migration) ──
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT,
    conversation_type TEXT DEFAULT 'direct',
    created_by TEXT NOT NULL REFERENCES users(id),
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_conv_created ON conversations(created_by);

CREATE TABLE IF NOT EXISTS conversation_participants (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id),
    role TEXT DEFAULT 'member',
    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    left_at DATETIME,
    UNIQUE(conversation_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_cp_conv ON conversation_participants(conversation_id);
CREATE INDEX IF NOT EXISTS idx_cp_user ON conversation_participants(user_id);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_id TEXT NOT NULL REFERENCES users(id),
    content TEXT NOT NULL,
    message_type TEXT DEFAULT 'text',
    metadata_json TEXT,
    is_read INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_msg_sender ON messages(sender_id);
CREATE INDEX IF NOT EXISTS idx_msg_created ON messages(created_at);

CREATE TABLE IF NOT EXISTS email_aliases (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    alias TEXT NOT NULL UNIQUE,
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ea_user ON email_aliases(user_id);
CREATE INDEX IF NOT EXISTS idx_ea_alias ON email_aliases(alias);

-- ── Registry tables (model exists, no migration) ──
CREATE TABLE IF NOT EXISTS registry_projects (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    description TEXT,
    chain TEXT,
    language TEXT DEFAULT 'solidity',
    version TEXT DEFAULT '1.0.0',
    tags TEXT,
    is_public INTEGER DEFAULT 1,
    is_verified INTEGER DEFAULT 0,
    star_count INTEGER DEFAULT 0,
    fork_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_rp_owner ON registry_projects(owner_id);
CREATE INDEX IF NOT EXISTS idx_rp_slug ON registry_projects(slug);

CREATE TABLE IF NOT EXISTS registry_abis (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES registry_projects(id) ON DELETE CASCADE,
    abi_json TEXT NOT NULL,
    abi_hash TEXT,
    source_type TEXT DEFAULT 'upload',
    compiler_version TEXT,
    is_verified INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ra_project ON registry_abis(project_id);

CREATE TABLE IF NOT EXISTS registry_sdks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES registry_projects(id) ON DELETE CASCADE,
    sdk_json TEXT NOT NULL,
    sdk_hash TEXT,
    language TEXT DEFAULT 'javascript',
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_rs_project ON registry_sdks(project_id);

CREATE TABLE IF NOT EXISTS execution_logic (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES registry_projects(id) ON DELETE CASCADE,
    function_name TEXT NOT NULL,
    logic_json TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_el_project ON execution_logic(project_id);

CREATE TABLE IF NOT EXISTS registry_stars (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES registry_projects(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, user_id)
);

CREATE TABLE IF NOT EXISTS registry_forks (
    id TEXT PRIMARY KEY,
    source_project_id TEXT NOT NULL REFERENCES registry_projects(id),
    forked_project_id TEXT NOT NULL REFERENCES registry_projects(id),
    forked_by TEXT NOT NULL REFERENCES users(id),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── Brain tables (model exists, no migration) ──
CREATE TABLE IF NOT EXISTS user_repositories (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    namespace TEXT NOT NULL UNIQUE,
    display_name TEXT,
    bio TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ur_user ON user_repositories(user_id);

CREATE TABLE IF NOT EXISTS contract_repos (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    repository_id TEXT REFERENCES user_repositories(id),
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    description TEXT,
    chain TEXT,
    address TEXT,
    language TEXT DEFAULT 'solidity',
    source_code TEXT,
    tags TEXT,
    is_public INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    sdk_enabled INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cr_user ON contract_repos(user_id);
CREATE INDEX IF NOT EXISTS idx_cr_public ON contract_repos(is_public);

CREATE TABLE IF NOT EXISTS contract_functions (
    id TEXT PRIMARY KEY,
    contract_id TEXT NOT NULL REFERENCES contract_repos(id) ON DELETE CASCADE,
    function_name TEXT NOT NULL,
    signature TEXT,
    selector TEXT,
    visibility TEXT,
    state_mutability TEXT,
    access_level TEXT,
    access_modifier TEXT,
    inputs_json TEXT,
    outputs_json TEXT,
    is_dangerous INTEGER DEFAULT 0,
    is_enabled INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cf_contract ON contract_functions(contract_id);

CREATE TABLE IF NOT EXISTS contract_events (
    id TEXT PRIMARY KEY,
    contract_id TEXT NOT NULL REFERENCES contract_repos(id) ON DELETE CASCADE,
    event_name TEXT NOT NULL,
    signature TEXT,
    topic_hash TEXT,
    inputs_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ce_contract ON contract_events(contract_id);

CREATE TABLE IF NOT EXISTS sdk_definitions (
    id TEXT PRIMARY KEY,
    contract_id TEXT NOT NULL REFERENCES contract_repos(id) ON DELETE CASCADE,
    sdk_json TEXT NOT NULL,
    sdk_hash TEXT,
    is_public INTEGER DEFAULT 0,
    chain TEXT,
    contract_address TEXT,
    generated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sd_contract ON sdk_definitions(contract_id);
CREATE INDEX IF NOT EXISTS idx_sd_public ON sdk_definitions(is_public);
CREATE INDEX IF NOT EXISTS idx_sd_address ON sdk_definitions(contract_address);

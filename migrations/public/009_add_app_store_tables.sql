-- Migration 009: Add App Store tables
-- App listings, reviews, and install tracking

CREATE TABLE IF NOT EXISTS app_listings (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    description TEXT,
    readme TEXT,
    category TEXT NOT NULL,
    chain TEXT,
    version TEXT DEFAULT '1.0.0',
    icon_url TEXT,
    screenshots TEXT,
    tags TEXT,
    registry_project_id TEXT,
    dapp_build_id TEXT,
    agent_id TEXT,
    install_count INTEGER DEFAULT 0,
    rating_avg REAL DEFAULT 0.0,
    rating_count INTEGER DEFAULT 0,
    is_published INTEGER DEFAULT 0,
    is_verified INTEGER DEFAULT 0,
    is_featured INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_al_owner_id ON app_listings(owner_id);
CREATE INDEX IF NOT EXISTS idx_al_slug ON app_listings(slug);
CREATE INDEX IF NOT EXISTS idx_al_category ON app_listings(category);
CREATE INDEX IF NOT EXISTS idx_al_chain ON app_listings(chain);
CREATE INDEX IF NOT EXISTS idx_al_published ON app_listings(is_published);
CREATE INDEX IF NOT EXISTS idx_al_featured ON app_listings(is_featured);

CREATE TABLE IF NOT EXISTS app_reviews (
    id TEXT PRIMARY KEY,
    app_id TEXT NOT NULL REFERENCES app_listings(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id),
    rating INTEGER NOT NULL,
    comment TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(app_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_ar_app_id ON app_reviews(app_id);
CREATE INDEX IF NOT EXISTS idx_ar_user_id ON app_reviews(user_id);

CREATE TABLE IF NOT EXISTS app_installs (
    id TEXT PRIMARY KEY,
    app_id TEXT NOT NULL REFERENCES app_listings(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id),
    installed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    uninstalled_at DATETIME,
    UNIQUE(app_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_ai_app_id ON app_installs(app_id);
CREATE INDEX IF NOT EXISTS idx_ai_user_id ON app_installs(user_id);

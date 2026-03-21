-- Download leads and waitlist signups for product download tracking
CREATE TABLE IF NOT EXISTS download_leads (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    eth_address TEXT,
    product TEXT NOT NULL,
    platform TEXT,
    version TEXT,
    user_id TEXT,
    referrer TEXT,
    ip_hash TEXT,
    user_agent TEXT,
    marketing_consent BOOLEAN DEFAULT 0,
    download_type TEXT DEFAULT 'download',
    embedding_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_download_leads_email ON download_leads(email);
CREATE INDEX IF NOT EXISTS idx_download_leads_product ON download_leads(product);
CREATE INDEX IF NOT EXISTS idx_download_leads_product_created ON download_leads(product, created_at);

-- CIFI Federated Identity columns on users table
-- Tracks verification status, username from CIFI, KYC level, and display name

ALTER TABLE users ADD COLUMN cifi_verified BOOLEAN DEFAULT 0;
ALTER TABLE users ADD COLUMN cifi_username VARCHAR UNIQUE;
ALTER TABLE users ADD COLUMN cifi_verified_at DATETIME;
ALTER TABLE users ADD COLUMN cifi_kyc_level VARCHAR;
ALTER TABLE users ADD COLUMN cifi_display_name VARCHAR;

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_cifi_username ON users(cifi_username);

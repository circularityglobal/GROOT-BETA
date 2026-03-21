-- Migration 019: Add onboarding timestamps, marketing consent, and CIFI federation columns to users
-- Date: 2026-03-20

ALTER TABLE users ADD COLUMN auth_layer_1_completed_at DATETIME;
ALTER TABLE users ADD COLUMN auth_layer_2_completed_at DATETIME;
ALTER TABLE users ADD COLUMN auth_layer_3_completed_at DATETIME;
ALTER TABLE users ADD COLUMN onboarding_completed_at DATETIME;
ALTER TABLE users ADD COLUMN marketing_consent BOOLEAN DEFAULT 0;
ALTER TABLE users ADD COLUMN marketing_consent_at DATETIME;
ALTER TABLE users ADD COLUMN cifi_verified BOOLEAN DEFAULT 0;
ALTER TABLE users ADD COLUMN cifi_username VARCHAR;
ALTER TABLE users ADD COLUMN cifi_verified_at DATETIME;
ALTER TABLE users ADD COLUMN cifi_kyc_level VARCHAR;
ALTER TABLE users ADD COLUMN cifi_display_name VARCHAR;

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_cifi_username ON users(cifi_username);

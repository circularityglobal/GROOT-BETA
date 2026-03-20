-- Onboarding tracking: timestamps for auth layer completions and marketing consent
ALTER TABLE users ADD COLUMN auth_layer_1_completed_at DATETIME;
ALTER TABLE users ADD COLUMN auth_layer_2_completed_at DATETIME;
ALTER TABLE users ADD COLUMN auth_layer_3_completed_at DATETIME;
ALTER TABLE users ADD COLUMN onboarding_completed_at DATETIME;
ALTER TABLE users ADD COLUMN marketing_consent BOOLEAN DEFAULT 0;
ALTER TABLE users ADD COLUMN marketing_consent_at DATETIME;

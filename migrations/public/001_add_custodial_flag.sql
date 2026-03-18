-- Add custodial wallet flag to users table
-- Indicates the user's wallet is server-managed (SSS-secured) rather than user-provided (MetaMask)
ALTER TABLE users ADD COLUMN is_custodial_wallet BOOLEAN DEFAULT 0;

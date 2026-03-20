---
paths:
  - "api/**/*.py"
  - "scripts/**/*.py"
---

# Security Rules

## Wallet & Key Handling
- Private keys MUST be zeroed from memory after use via `ctypes.memset`
- All wallet signing goes through `sign_transaction_with_groot_wallet()` — never reconstruct keys directly
- SSS shares are encrypted with AES-256-GCM using per-wallet HKDF-derived keys
- GROOT wallet operations require `_require_master_admin()` gate — admin secret header cannot bypass

## Data Isolation
- `internal.db` tables (ServerSecret, RoleAssignment, AdminAuditLog, CustodialWallet, WalletShare) are NEVER exposed via public API
- User source code (`ContractRepo.source_code`) is NEVER included in API responses or GROOT context
- GROOT only sees public SDK definitions (`SDKDefinition.is_public == True`)

## Authentication
- Tier 2 actions (deploy, transfer, state-changing calls) require PendingAction + master_admin approval
- Admin secret usage is audited in `admin_audit_log` with method, path, and IP
- Sensitive operations (API keys, provider keys) require all 3 auth layers complete (SIWE + Password + TOTP)

## Input Validation
- Always validate chain names via `ChainRegistry` or fallback dict — never trust user chain strings directly
- Contract addresses must be checksummed via `Web3.to_checksum_address()`
- ABI JSON validated via `json.loads()` before storage

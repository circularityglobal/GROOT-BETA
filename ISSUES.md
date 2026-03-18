# SIWE Communication Infrastructure — Issue Tracker

All 4 phases pass 52/52 functional tests. These are code quality, performance, and hardening issues to address in a follow-up session.

## Priority: HIGH

### H1. ~~SIWE URI Format Mismatch (Phase 1)~~ ✅ RESOLVED
- **File:** `frontend/components/AuthFlow/index.tsx:119`
- **Resolution:** Frontend now uses `URI: https://${domain}` matching backend format.

### H2. ~~N+1 Query in `get_conversations()` (Phase 3)~~ ✅ RESOLVED
- **File:** `api/services/messaging.py:185-220`
- **Resolution:** Replaced per-conversation unread count loop with two bulk queries using OR filters. Now 4 total queries regardless of conversation count.

### H3. ~~N+1 Query in `_find_existing_dm()` (Phase 3)~~ ✅ RESOLVED
- **File:** `api/services/messaging.py:453-475`
- **Resolution:** Uses subquery JOIN to find DM in a single query.

### H4. ~~`get_messages()` Return Type Annotation Wrong (Phase 4 audit)~~ ✅ RESOLVED
- **File:** `api/services/messaging.py:338`
- **Resolution:** Return type correctly declared as `tuple[list[Message], bool]`.

## Priority: MEDIUM

### M1. ~~Stale Peer Index Entries on Update (Phase 4)~~ ✅ RESOLVED
- **File:** `api/services/p2p.py:110-114`
- **Resolution:** Old index entries removed before adding new ones when address/IPv6 changes.

### M2. ~~`cleanup_stale_peers()` Never Called (Phase 4)~~ ✅ RESOLVED
- **File:** `api/main.py:70-80`
- **Resolution:** Background task `_p2p_cleanup_loop` runs every 60 seconds.

### M3. ~~Typing Dict Memory Leak (Phase 4)~~ ✅ RESOLVED
- **File:** `api/services/p2p.py:274-275`
- **Resolution:** Empty conversation dicts deleted when last entry expires.

### M4. ENS Cache Invalidation Incomplete (Phase 2)
- **File:** `api/auth/ens.py:260-264`
- **Issue:** `invalidate_ens_cache()` doesn't clear `fwd:` cache keys (forward name→address lookups).
- **Status:** Accepted limitation — ENS name→address mappings rarely change. Forward cache entries expire via TTL.

### M5. ~~No Rate Limiting on Messaging Routes (Phase 3)~~ ✅ RESOLVED
- **File:** `api/routes/messaging.py`
- **Resolution:** Added `@limiter.limit()` decorators to all messaging endpoints (30-60/min for reads, 10/min for writes).

### M6. ~~Missing Group Permission Check Not Logged (Phase 3)~~ ✅ RESOLVED
- **File:** `api/services/messaging.py:493-500`
- **Resolution:** Error messages distinguish between "groups disabled" and "blocklisted" with specific logging.

## Priority: LOW

### L1. ~~Sepolia Chain Name Mismatch (Phase 1)~~ ✅ RESOLVED
- Both backend and frontend use "Sepolia".

### L2. Missing `ens_email` Column (Phase 2)
- **File:** `api/models/public.py`
- **Status:** Column exists in WalletIdentity model. Resolved.

### L3. Unused `wallet_to_pseudo_ipv6()` in network_identity.py (Phase 2)
- **File:** `api/auth/network_identity.py:34-47`
- **Status:** Low priority — legacy utility function. May be useful for external integrations.

### L4. In-Memory Indexes Not Thread-Safe (Phase 2)
- **File:** `api/auth/network_identity.py:114-129`
- **Status:** Acceptable for single-process SQLite deployment. GIL protects simple dict operations.

### L5. Unused `_on_presence_change` Callback List (Phase 4)
- **File:** `api/services/p2p.py:87`
- **Status:** Low priority dead code.

### L6. ~~`asyncio.get_event_loop()` in Sync Routes (Phase 4)~~ ✅ RESOLVED
- **File:** `api/services/smtp_bridge.py:163`
- **Resolution:** Changed to `asyncio.get_running_loop()`.

### L7. ~~Local Import in `resolve_recipient()` (Phase 3)~~ ✅ RESOLVED
- **File:** `api/services/messaging.py`
- **Resolution:** `EmailAlias` imported at module top level.

### L8. ENS Resolution Blocks Login (Phase 1/2)
- **File:** `api/auth/wallet_identity.py:144-145`
- **Status:** Low priority — ENS resolution has cache with 1-hour TTL. Slow ENS provider only affects first login.

### L9. Missing `public_key` in Identity Response (Phase 1)
- **File:** `api/schemas/auth.py`
- **Status:** Intentional — will be exposed when implementing E2EE.

### L10. ~~Peer `eth_address` Not Updated on Re-register (Phase 4)~~ ✅ RESOLVED
- **File:** `api/services/p2p.py:115`
- **Resolution:** `existing.eth_address = eth_address` added in update branch.

## Test Results Summary

```
Phase 1 (Multi-Chain SIWE):      10/10 PASS
Phase 2 (ENS + Network ID):      12/12 PASS
Phase 3 (Messaging + Email):     13/13 PASS
Phase 4 (P2P + SMTP Bridge):     17/17 PASS
─────────────────────────────────────────────
Total:                            52/52 PASS
```

## Summary

**Resolved:** H1, H2, H3, H4, M1, M2, M3, M5, M6, L1, L2, L6, L7, L10 (14 of 20)
**Accepted/Deferred:** M4, L3, L4, L5, L8, L9 (6 remaining — all low risk)

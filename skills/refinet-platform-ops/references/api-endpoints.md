# REFINET Cloud API Endpoints Reference

This is the quick-reference for the platform-ops agent. For full docs see `docs/API_REFERENCE.md` in the repo.

## Auth Requirements

| Level | What It Means | Required For |
|---|---|---|
| None | Public access | `/health`, `/explore/*` |
| JWT | Signed in via SIWE or password | Most endpoints |
| API Key | `rf_` prefixed key in Authorization header | `/v1/*`, programmatic access |
| Full Auth | SIWE + Password + TOTP (all 3 layers) | `/keys/*`, `/provider-keys/*` |
| Admin | JWT with admin role | `/admin/*` |
| Device Key | Device-specific auth token | `/devices/*` |
| Build Key | Agent build authentication | `/agents/*` (write) |

## Route Groups Summary (22 groups, 210+ endpoints)

### Health & Root (2 endpoints)
- `GET /` — Platform info
- `GET /health` — Comprehensive health check (API, DB, inference, SMTP, scheduler)

### Auth (19 endpoints)
- `POST /auth/siwe/nonce` — Get SIWE nonce
- `POST /auth/siwe/verify` — Verify SIWE signature
- `POST /auth/register` — Email/password registration
- `POST /auth/login` — Email/password login
- `POST /auth/totp/setup` — Enable TOTP 2FA
- `POST /auth/totp/verify` — Verify TOTP code
- `GET /auth/me` — Current user profile
- `POST /auth/logout` — Invalidate session

### AI Inference (3 endpoints)
- `POST /v1/chat/completions` — OpenAI-compatible chat (all providers)
- `GET /v1/models` — List available models
- `POST /v1/embeddings` — Generate embeddings

### Agents (12+ endpoints)
- `POST /agents` — Register agent
- `GET /agents` — List agents
- `GET /agents/{id}` — Agent details
- `POST /agents/{id}/tasks` — Submit task
- `GET /agents/{id}/memory` — Read agent memory
- `POST /agents/{id}/delegate` — Agent-to-agent delegation

### Knowledge Base (5+ endpoints)
- `POST /knowledge/upload` — Upload document
- `POST /knowledge/search` — Semantic search
- `GET /knowledge/documents` — List documents
- `DELETE /knowledge/documents/{id}` — Remove document
- `POST /knowledge/youtube` — Ingest YouTube transcript

### Smart Contract Registry (12+ endpoints)
- `POST /registry/projects` — Create project
- `POST /registry/projects/{id}/abis` — Upload ABI
- `GET /registry/explore` — Public explorer
- `POST /registry/projects/{id}/star` — Star project
- `POST /registry/projects/{id}/fork` — Fork project

### Messages (8+ endpoints)
- `POST /messages/send` — Send wallet-to-wallet message
- `GET /messages/conversations` — List conversations
- `GET /messages/conversations/{id}` — Get messages
- `POST /messages/groups` — Create group

### Chain Listener (6+ endpoints)
- `POST /chain/listeners` — Create event listener
- `GET /chain/listeners` — List listeners
- `GET /chain/events` — Get captured events

### Admin (14+ endpoints)
- `GET /admin/stats` — Platform statistics
- `GET /admin/users` — User management
- `GET /admin/audit-log` — Append-only audit log
- `POST /admin/scripts/{name}/run` — Execute operational script

## Rate Limits

| Tier | Limit | Auth |
|---|---|---|
| Anonymous | 25 req/day | None |
| Authenticated | 250 req/day | JWT |
| API Key | Per-key configurable | API key |
| Admin | Unlimited | Admin JWT |

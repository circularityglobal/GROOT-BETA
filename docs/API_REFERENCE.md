# REFINET Cloud API Reference
## Version 3.1 · March 2026

> Every endpoint documented here has been verified against the source code. Request/response schemas, authentication requirements, and security constraints are extracted directly from the codebase — not written from memory or specification.

---

## Base URL

| Environment | URL |
|------------|-----|
| Production | `https://api.refinet.io` |
| Development | `http://localhost:8000` |

## Authentication

Three methods are supported across all endpoints:

| Method | Header | Format | Scope |
|--------|--------|--------|-------|
| JWT | `Authorization: Bearer <token>` | Issued via SIWE or password login | Full user scopes |
| API Key | `Authorization: Bearer rf_<key>` | Created via `POST /keys` | Scoped (e.g., `inference:read`) |
| Anonymous | (none) | IP-based rate limiting | Inference only (25 req/day) |

### Security Layers

Sensitive operations (API keys, provider keys) require **all three layers** complete:

| Layer | How to Complete | Required For |
|-------|----------------|-------------|
| Layer 3: SIWE | Sign in with Ethereum wallet | Platform access |
| Layer 1: Password | Set email + password in Settings → Security | Key management |
| Layer 2: TOTP | Enable 2FA in Settings → Security | Key management |

If layers are incomplete, the API returns:

```json
{
  "detail": {
    "error": "security_layers_required",
    "missing_layers": ["password", "totp"],
    "instructions": {
      "password": "Set an email and password in Settings → Security",
      "totp": "Enable 2FA (TOTP) in Settings → Security"
    }
  }
}
```

---

## 1. Inference (OpenAI-Compatible)

### GET /v1/models

List all available models from all registered providers. No auth required.

**Response:**
```json
{
  "object": "list",
  "data": [
    {
      "id": "bitnet-b1.58-2b",
      "object": "model",
      "created": 1710000000,
      "owned_by": "refinet",
      "provider": "refinet",
      "context_window": 2048,
      "is_free": true
    },
    {
      "id": "gemini-2.0-flash",
      "object": "model",
      "created": 1710000000,
      "owned_by": "google",
      "provider": "gemini",
      "context_window": 1048576,
      "is_free": true
    }
  ]
}
```

### POST /v1/chat/completions

Create a chat completion. Compatible with OpenAI SDK.

**Auth:** JWT, API key, or anonymous (25 req/day, max 256 tokens)

**Request:**
```json
{
  "model": "bitnet-b1.58-2b",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is regenerative finance?"}
  ],
  "temperature": 0.7,
  "max_tokens": 512,
  "top_p": 1.0,
  "stream": false,
  "grounding": false,
  "notebook_doc_ids": null
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | string | `"bitnet-b1.58-2b"` | Model ID. Use any model from `/v1/models` or from a BYOK provider. |
| `messages` | array | required | OpenAI-format messages (`role`: system/user/assistant) |
| `temperature` | float | 0.7 | 0.0 - 2.0 |
| `max_tokens` | int | 512 | 1 - 4096 |
| `top_p` | float | 1.0 | 0.0 - 1.0 |
| `stream` | bool | false | Enable SSE streaming |
| `grounding` | bool | false | Enable Google Search grounding (Gemini models only) |
| `notebook_doc_ids` | array | null | Scope RAG to specific document IDs |

**Response (non-streaming):**
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1710000000,
  "model": "bitnet-b1.58-2b",
  "provider": "bitnet",
  "choices": [{
    "index": 0,
    "message": {"role": "assistant", "content": "Regenerative finance..."},
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 42,
    "completion_tokens": 128,
    "total_tokens": 170
  },
  "sources": [
    {
      "document_id": "doc-123",
      "document_title": "ReFi Overview",
      "category": "about",
      "score": 0.87,
      "preview": "Regenerative finance is a framework..."
    }
  ]
}
```

**Multi-model examples:**
```python
# BitNet (sovereign, free, default)
client.chat.completions.create(model="bitnet-b1.58-2b", messages=[...])

# Google Gemini with web grounding
client.chat.completions.create(model="gemini-2.0-flash", messages=[...], extra_body={"grounding": True})

# OpenAI (requires BYOK key saved in Settings → AI Services)
client.chat.completions.create(model="gpt-4o", messages=[...])

# Anthropic (requires BYOK key)
client.chat.completions.create(model="claude-sonnet-4-6", messages=[...])

# OpenRouter (free models available)
client.chat.completions.create(model="meta-llama/llama-3.1-8b-instruct:free", messages=[...])
```

---

## 2. Provider Keys (BYOK — Bring Your Own Key)

Connect your own API keys for external AI providers. All mutating endpoints require full 3-layer auth.

### GET /provider-keys/catalog

List all 13 supported AI providers. No auth required.

**Response:** Array of provider objects:
```json
[
  {
    "type": "openai",
    "name": "OpenAI",
    "description": "GPT-4o, GPT-4o-mini, DALL-E 3, Whisper, TTS",
    "category": "llm",
    "capabilities": ["chat", "image", "audio", "embedding"],
    "auth_type": "api_key",
    "key_url": "https://platform.openai.com/api-keys",
    "base_url": "https://api.openai.com",
    "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
    "free_tier": false
  }
]
```

### GET /provider-keys/security-status

Check if user has completed all 3 security layers. Requires JWT.

**Response:**
```json
{
  "layer_1_complete": true,
  "layer_2_complete": false,
  "layer_3_complete": true,
  "all_layers_complete": false,
  "can_manage_keys": false
}
```

### GET /provider-keys

List user's saved provider keys (masked). Requires full 3-layer auth.

### POST /provider-keys

Save or update an external provider key. Requires full 3-layer auth.

**Request:**
```json
{
  "provider_type": "openai",
  "display_name": "My OpenAI Key",
  "api_key": "sk-proj-...",
  "base_url": null
}
```

### DELETE /provider-keys/{key_id}

Delete a provider key. Requires full 3-layer auth.

### POST /provider-keys/{key_id}/test

Test a provider key connection. Returns latency and status. Requires full 3-layer auth.

**Response:**
```json
{
  "status": "ok",
  "latency_ms": 245,
  "provider": "openai",
  "message": "Connection successful"
}
```

---

## 3. API Key Management

### POST /keys

Create a new platform API key. Requires full 3-layer auth + `keys:write` scope.

**Request:**
```json
{
  "name": "my-app-key",
  "scopes": "inference:read",
  "daily_limit": 100
}
```

**Response:** Returns the key **once** — it cannot be recovered after this response.
```json
{
  "id": "uuid",
  "key": "rf_a1b2c3...",
  "prefix": "rf_a1b2c3d4e5",
  "name": "my-app-key",
  "scopes": "inference:read",
  "daily_limit": 100,
  "message": "Save this key — it won't be shown again."
}
```

### GET /keys

List active API keys (masked). Requires full 3-layer auth.

### DELETE /keys/{key_id}

Revoke an API key. Requires full 3-layer auth.

### GET /keys/activity

Last 5 usage records. Basic auth only.

---

## 4. Authentication

### GET /auth/siwe/nonce

Get a nonce + message template for SIWE signing. Public.

### POST /auth/siwe/verify

Verify SIWE signature and create/login account. Public.

**Request:**
```json
{
  "message": "app.refinet.io wants you to sign in...",
  "signature": "0x...",
  "nonce": "abc123...",
  "chain_id": 1
}
```

### POST /auth/settings/password

Set email and password (Layer 1). Requires JWT.

### POST /auth/settings/totp/setup

Initialize TOTP 2FA setup. Returns QR code. Requires JWT.

### POST /auth/settings/totp/verify

Verify TOTP code to enable 2FA (Layer 2). Requires JWT.

### POST /auth/login

Password login. Returns JWT (or partial token if TOTP enabled). Public.

### POST /auth/login/totp

Complete password login with TOTP code. Requires partial JWT.

### POST /auth/token/refresh

Rotate refresh token. Returns new access token. Public.

### POST /auth/logout

Revoke all refresh tokens. Requires JWT.

### GET /auth/me

Get current user profile. Requires JWT.

---

## 5. Knowledge Base (RAG)

### POST /knowledge/ingest

Upload a document for RAG. Supports PDF, DOCX, XLSX, CSV, TXT, MD, JSON, Solidity.

### GET /knowledge/documents

List user's knowledge documents.

### GET /knowledge/search

Hybrid search: semantic similarity + keyword scoring + FTS5 full-text.

---

## 6. Agent Engine

### POST /agents/register

Register an agent. Requires JWT.

### POST /agents/{agent_id}/run

Submit a task for autonomous execution. Requires JWT.

### GET /agents/{agent_id}/tasks/{task_id}

Get task detail with execution trace, plan, steps, tokens used.

---

## 7. Smart Contract Registry

### POST /registry/projects

Create a registry project. Requires `registry:write` scope.

### GET /registry/projects

Search/browse projects. Public.

### POST /registry/projects/{slug}/abis

Upload an ABI. Auto-parses functions, events, access control.

### POST /registry/projects/{slug}/sdks

Generate SDK from parsed ABI.

---

## 8. App Store

### GET /apps

Browse and search published apps. Public.

### POST /apps

Publish an app (DApp, agent, tool, template). Requires JWT.

### POST /apps/submissions

Create a submission for the review pipeline (draft → scan → review → publish).

---

## 9. Admin (Role-Gated)

### GET /admin/providers

List all model providers with health status, config, and models.

### GET /admin/providers/health

Force health check on all providers.

### GET /admin/providers/usage

Usage breakdown by provider (calls, tokens, latency).

### GET /admin/stats

Platform stats (users, devices, agents, inference calls, webhooks).

### GET /admin/users

List all users with roles and auth layer status.

---

## Environment Variables

All optional provider config (empty = disabled):

```bash
# Sovereign Model (always active)
BITNET_HOST=http://127.0.0.1:8080

# Cloud Providers
GEMINI_API_KEY=
OPENROUTER_API_KEY=

# Local Providers
OLLAMA_HOST=
LMSTUDIO_HOST=

# Gateway Config
DEFAULT_MODEL=bitnet-b1.58-2b
PROVIDER_FALLBACK_CHAIN=bitnet,gemini,ollama,lmstudio,openrouter

# Gemini Rate Limits (free tier)
GEMINI_FLASH_RPM=15
GEMINI_PRO_RPM=2
GEMINI_FLASH_DAILY_LIMIT=1500
GEMINI_PRO_DAILY_LIMIT=50

# Security
ADMIN_WALLET=0xE302932D42C751404AeD466C8929F1704BA89D5A
```

---

## Rate Limits

| Tier | Daily Requests | Per Minute | Max Tokens |
|------|---------------|-----------|-----------|
| Anonymous | 25 | 5 | 256 |
| Free (authenticated) | 250 | 60 | 4096 |
| Developer | 250+ (configurable) | 60 | 4096 |
| API Key | Per-key limit (default 250) | 60 | 4096 |

---

## Supported Chains

| Chain | Chain ID | SIWE | Registry |
|-------|---------|------|---------|
| Ethereum Mainnet | 1 | Yes | Yes |
| Polygon | 137 | Yes | Yes |
| Arbitrum One | 42161 | Yes | Yes |
| Optimism | 10 | Yes | Yes |
| Base | 8453 | Yes | Yes |
| Sepolia (testnet) | 11155111 | Yes | Yes |

---

## How BYOK Works (End-to-End)

1. **Sign in** with your Ethereum wallet (Layer 3)
2. **Set email + password** in Settings → Security (Layer 1)
3. **Enable TOTP 2FA** in Settings → Security (Layer 2)
4. **Go to Settings → AI Services** — all 3 layers complete, panel unlocks
5. **Click a provider** (e.g., OpenAI) → enter your API key → Save
6. **Test the connection** — green checkmark confirms it works
7. **Go to Chat** → select model (e.g., `gpt-4o`) from the model selector
8. **Send a message** — the platform decrypts your key, creates an ephemeral provider, and routes the request through your own API key
9. **Platform keys are never touched** — your key, your billing, your data

---

## Security Model

```
                    ┌─────────────────────────────────┐
                    │   REFINET Cloud Security Layers   │
                    ├─────────────────────────────────┤
  Layer 3 (SIWE)   │ Wallet signature → platform access │
  Layer 1 (Pass)   │ Argon2id hash → account recovery   │
  Layer 2 (TOTP)   │ 2FA code → compromise protection   │
                    ├─────────────────────────────────┤
  Full Auth Gate    │ All 3 required for:               │
                    │  • Creating API keys              │
                    │  • Saving provider keys            │
                    │  • Using BYOK in inference         │
                    │  • Listing stored keys             │
                    └─────────────────────────────────┘
```

**Encryption:** AES-256-GCM for all stored secrets (TOTP keys, provider keys, wallet shares). Key previews computed at save time — encrypted keys are never decrypted for display.

**Audit:** All admin operations logged to append-only `AdminAuditLog`. Provider key access tracked with usage counts and timestamps.

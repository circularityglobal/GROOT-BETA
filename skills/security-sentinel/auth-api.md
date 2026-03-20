# REFINET Authentication & Security API Reference

## Auth Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/siwe/nonce` | None | Get SIWE nonce for message signing |
| `POST` | `/auth/siwe/verify` | None | Verify SIWE signature, issue JWT |
| `POST` | `/auth/register` | None | Register with email + password |
| `POST` | `/auth/login` | None | Login with email + password |
| `POST` | `/auth/totp/setup` | JWT | Enable TOTP 2FA (returns QR code) |
| `POST` | `/auth/totp/verify` | JWT | Verify TOTP code |
| `GET` | `/auth/totp/status` | JWT | Check if TOTP is enabled |
| `POST` | `/auth/password/set` | JWT | Set password (for SIWE-only users) |
| `POST` | `/auth/password/change` | JWT | Change existing password |
| `POST` | `/auth/token/refresh` | JWT | Refresh access token |
| `POST` | `/auth/logout` | JWT | Invalidate session |
| `GET` | `/auth/me` | JWT | Current user profile + auth layers status |

## Key Management Endpoints (BYOK Gate Protected)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/keys/create` | Full Auth | Create new API key |
| `GET` | `/keys/` | Full Auth | List user's API keys |
| `DELETE` | `/keys/{id}` | Full Auth | Revoke API key |
| `POST` | `/provider-keys/save` | Full Auth | Save external LLM provider key |
| `GET` | `/provider-keys/` | Full Auth | List saved provider keys |
| `DELETE` | `/provider-keys/{id}` | Full Auth | Remove provider key |

**Full Auth** = SIWE verified + Password set + TOTP enabled. Missing any layer returns 403.

## Admin Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/admin/audit-log` | Admin | Query append-only audit log |
| `GET` | `/admin/stats` | Admin | Platform statistics |
| `GET` | `/admin/users` | Admin | User management |
| `GET` | `/admin/users/{id}` | Admin | User details + auth layers |
| `POST` | `/admin/scripts/{name}/run` | Admin | Execute operational script |

## Audit Log Query Parameters

```
GET /admin/audit-log?
  event_type=auth.siwe.fail&     # Filter by event type
  ip_address=1.2.3.4&            # Filter by IP
  wallet_address=0xabc...&       # Filter by wallet
  user_id=user_123&              # Filter by user
  since=2025-03-01T00:00:00Z&   # Start date
  until=2025-03-15T00:00:00Z&   # End date
  limit=100&                     # Max results (default 50)
  offset=0                       # Pagination offset
```

## JWT Scope Types (12)

| Scope | Access Level |
|---|---|
| `chat` | AI inference endpoints |
| `registry.read` | Read smart contract registry |
| `registry.write` | Create/edit registry projects |
| `knowledge.read` | Search knowledge base |
| `knowledge.write` | Upload documents |
| `messages.read` | Read messages |
| `messages.write` | Send messages |
| `chain.read` | Query chain events |
| `chain.write` | Create chain listeners |
| `devices.read` | Read device telemetry |
| `devices.write` | Register devices |
| `admin` | Full admin access |

## Audit Log Database Schema

```sql
CREATE TABLE audit_log (
    id TEXT PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT NOT NULL,
    user_id TEXT,
    wallet_address TEXT,
    ip_address TEXT,
    user_agent TEXT,
    endpoint TEXT,
    method TEXT,
    status_code INTEGER,
    details JSON,
    risk_level TEXT DEFAULT 'none'
);

CREATE INDEX idx_audit_event ON audit_log(event_type, timestamp);
CREATE INDEX idx_audit_ip ON audit_log(ip_address, timestamp);
CREATE INDEX idx_audit_wallet ON audit_log(wallet_address, timestamp);
CREATE INDEX idx_audit_user ON audit_log(user_id, timestamp);
```

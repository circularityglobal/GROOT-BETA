---
name: refinet-security-sentinel
description: >
  REFINET Cloud security sentinel skill for autonomous defense, authentication
  anomaly detection, rate limit intelligence, TLS monitoring, and wallet forensics.
  Use this skill whenever the user wants to: audit platform security, detect auth
  anomalies, monitor SIWE wallet activity, analyze rate limit patterns, check TLS
  certificate expiry, validate the BYOK security gate, review the append-only audit
  log, investigate suspicious wallet behavior, monitor JWT token usage, detect
  credential stuffing, scan for privilege escalation, or build autonomous security
  monitoring workflows on REFINET Cloud. Triggers on phrases like "security audit",
  "auth anomaly", "SIWE forensics", "wallet behavior", "rate limit abuse",
  "TLS certificate", "cert expiry", "BYOK gate", "security gate validation",
  "audit log analysis", "brute force detection", "TOTP brute force", "API key abuse",
  "JWT reuse", "credential stuffing", "privilege escalation", "security sentinel",
  "security briefing", "auth scan", "IP analysis", "rate limit intelligence",
  "security agent", "defense system", "platform security", "wallet forensics",
  "suspicious activity", or any request to secure, defend, audit, or monitor
  authentication and authorization on the GROOT-BETA / REFINET Cloud platform.
---

# REFINET Security Sentinel — Autonomous Defense System Skill

This skill gives Claude everything needed to:
1. Detect authentication anomalies across all 3 auth layers (SIWE + Password + TOTP)
2. Monitor rate limit patterns and distinguish legitimate traffic from deliberate abuse
3. Track TLS certificate lifecycle and alert before expiry
4. Conduct wallet-level forensics on SIWE-authenticated sessions
5. Validate the BYOK Security Gate enforcement continuously
6. Send structured security briefing emails with threat classifications

The sentinel observes and reports — it never blocks, bans, or modifies. All enforcement requires explicit admin approval.

---

## Part 1 — Security Architecture

### 1.1 The Authentication Stack

```
Request arrives
  ├── Layer 1: SIWE (Sign-In with Ethereum) — EIP-4361 + nonce replay protection
  ├── Layer 2: Password (Optional) — Argon2id, per-user salt + server pepper
  ├── Layer 3: TOTP 2FA (Optional) — Google Authenticator compatible
  └── JWT issuance — 12 scope types, role-based (admin/operator/readonly)
```

### 1.2 The BYOK Security Gate

Creating API keys or saving provider keys requires ALL THREE layers. Incomplete auth returns HTTP 403 with specific guidance on which layer is missing.

### 1.3 Rate Limit Tiers

| Tier | Limit | Auth |
|---|---|---|
| Anonymous | 25 req/day | None (per-IP) |
| Authenticated | 250 req/day | JWT (per-user) |
| API Key | Configurable | Per-key |
| Admin | Unlimited | Admin JWT |

### 1.4 Audit Log

Append-only (no delete/update routes). Tracks: SIWE nonce/verify/fail, login/fail, TOTP verify/fail, token refresh/expired, key create/revoke, provider key save, rate limit hits, admin actions.

---

## Part 2 — Detection Pipelines

### 2.1 Auth Anomaly Detection Rules

| Rule | Pattern | Severity | Window |
|---|---|---|---|
| SIWE brute force | 5+ failed signatures from same IP | HIGH | 1 hour |
| TOTP brute force | 3+ TOTP failures for same user | CRITICAL | 30 min |
| Expired JWT reuse | 3+ expired token attempts per user/IP | MEDIUM | 1 hour |
| Credential stuffing | 3+ unique users, 10+ attempts from same IP | CRITICAL | 1 hour |
| API key abuse | 10+ rate limit hits for same key | HIGH | 1 hour |
| Admin access anomaly | Any admin endpoint access | MEDIUM | 24 hours |

### 2.2 Rate Limit Intelligence

Classifies rate limit patterns as NORMAL, TRAFFIC_SPIKE, or LIKELY_ABUSE based on: total hits, IP concentration (single IP >50% of hits = abuse), IP diversity, and hourly distribution.

### 2.3 TLS Certificate Monitoring

Checks cert expiry for api.refinet.io and app.refinet.io. Alert levels: CRITICAL (7 days), HIGH (14 days), MEDIUM (30 days), OK (30+ days).

### 2.4 SIWE Wallet Forensics

Flags wallets with: endpoint sweeping (50+ unique endpoints), multi-IP usage (5+ IPs), high error rates (30%+), rate limit abuse (3+ hits).

### 2.5 BYOK Gate Validation

Periodically tests that unauthenticated requests to /keys/* and /provider-keys/* return 403.

---

## Part 3 — Alert Categories

| Category | Subject Prefix | When |
|---|---|---|
| AUTH_ANOMALY | `[REFINET SECURITY]` | Anomaly detection rule triggered |
| RATE_ABUSE | `[REFINET SECURITY]` | Rate limit pattern classified as abuse |
| TLS_EXPIRY | `[REFINET SECURITY]` | Certificate within 30 days of expiry |
| WALLET_FLAG | `[REFINET SECURITY]` | Wallet forensics anomaly detected |
| GATE_FAIL | `[REFINET SECURITY]` | BYOK Security Gate test failed |
| BRIEFING | `[REFINET SECURITY]` | Daily security briefing digest |

---

## Part 4 — Cron Schedule

```yaml
# configs/security-sentinel-cron.yaml
schedules:
  - name: auth-scan
    interval: 15m
    agent: security-sentinel
    task: "Run all anomaly detection rules. Alert admin for CRITICAL/HIGH."

  - name: rate-analysis
    interval: 1h
    agent: security-sentinel
    task: "Analyze rate limit patterns. Classify and alert if LIKELY_ABUSE."

  - name: daily-briefing
    cron: "0 5 * * *"
    agent: security-sentinel
    task: "Compile 24h security briefing: anomalies, rates, TLS, wallets, gate. Email admin."

  - name: tls-check
    cron: "0 4 * * 0"
    agent: security-sentinel
    task: "Check TLS cert expiry. Alert at 30/14/7 days. CRITICAL if expired."

  - name: gate-validation
    cron: "30 4 * * 0"
    agent: security-sentinel
    task: "Validate BYOK gate returns 403 for incomplete auth. Alert on failure."

  - name: wallet-forensics
    cron: "0 5 * * 0"
    agent: security-sentinel
    task: "Analyze all SIWE wallets from past 7 days. Flag anomalous behavior."
```

---

## Part 5 — Operating Procedures

### 5.1 When User Asks to Audit Security
Run all detection pipelines, compile full report, email admin.

### 5.2 When User Reports Suspicious Activity
Query audit log for the wallet/IP, run forensics, present timeline with classifications, recommend actions.

### 5.3 When a Security Incident is Detected
Log to episodic memory, send CRITICAL email, recommend specific actions. Do NOT take destructive actions autonomously.

---

## Part 6 — Safety Constraints

- The sentinel observes and reports — it never blocks, bans, or modifies
- Never expose full API keys or JWT tokens in alerts — truncate to 8 chars
- Never expose wallet private keys, seed phrases, or Shamir shares
- Never disable security features
- Never bypass authentication or escalate privileges
- Reads but never writes to the audit log
- All enforcement requires explicit admin approval

---

## Part 7 — Reference Files

- `references/auth-api.md` — Auth endpoints, audit log schema, JWT scopes
- `references/threat-patterns.md` — Threat pattern catalog with SQL detection queries

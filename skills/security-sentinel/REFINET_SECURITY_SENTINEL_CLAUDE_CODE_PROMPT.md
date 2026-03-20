# REFINET Security Sentinel — Claude Code Installation Prompt

> **Copy everything below the line into Claude Code as a single prompt.**
> Run from inside your cloned `GROOT-BETA/` repo directory.
> Drop the 5 skill files from the `refinet-security-sentinel/` folder into the conversation.

---

## The Prompt

```
You are operating inside the GROOT-BETA repository (https://github.com/circularityglobal/GROOT-BETA), which is the REFINET Cloud sovereign AI platform. Your job is to install the `refinet-security-sentinel` skill — the fourth and final autonomous agent skill, completing the platform's zero-cost defense system. Follow every step precisely. Do not skip steps. Do not ask for confirmation — execute sequentially.

## CONTEXT

REFINET Cloud runs on a single ARM server (Oracle Cloud Always Free) with no WAF, no redundancy, and a 210+ endpoint attack surface across 6 protocols (REST, GraphQL, gRPC, SOAP, WebSocket, Webhooks). The auth system uses SIWE (EIP-4361) + optional Argon2id password + optional TOTP 2FA. The BYOK Security Gate requires all 3 layers to manage API keys. The audit log is append-only. Rate limits are tiered (25 anon, 250 auth, configurable per key, unlimited admin).

Three agent skills are already installed:
- `skills/refinet-platform-ops/` — Infrastructure health, heartbeat, admin alerts
- `skills/refinet-knowledge-curator/` — RAG/CAG intelligence, embedding quality
- `skills/refinet-contract-watcher/` — On-chain events, ABI security, bridge correlation

This final skill completes the autonomous defense layer. Same pattern: SKILL.md + scripts/ + references/, reuses run_agent.sh, same email alerting, zero cost.

## STEP 1 — Install the skill files

### 1a. Create `skills/refinet-security-sentinel/SKILL.md`

Main skill file covering the full autonomous defense system: 3-layer auth architecture, BYOK gate mechanics, rate limit tiers, audit log schema, 6 anomaly detection rules (SIWE brute force, TOTP brute force, credential stuffing, expired JWT reuse, API key abuse, rapid key creation), rate limit intelligence with abuse classification, TLS certificate monitoring, SIWE wallet forensics with 4 anomaly flags, BYOK gate validation, threat severity matrix, cron schedule with 6 tasks, and operating procedures. Read the provided file and copy exactly.

### 1b. Create `skills/refinet-security-sentinel/scripts/security_scan.py`

The autonomous defense scanner. Features: runs all 6 anomaly detection rules against the audit log, analyzes rate limit patterns and classifies as NORMAL/TRAFFIC_SPIKE/LIKELY_ABUSE, checks TLS cert expiry for api.refinet.io and app.refinet.io, runs wallet forensics on all active SIWE wallets, validates BYOK gate enforcement, generates HTML email report. Supports flags: --email, --tls-only, --gate-only, --wallet 0x... Read and copy exactly.

### 1c. Create `skills/refinet-security-sentinel/references/auth-api.md`

Auth API reference: all auth endpoints (SIWE, password, TOTP, token), key management endpoints (BYOK gate protected), admin endpoints (audit log, stats, users), audit log query parameters, 12 JWT scope types, and audit_log database schema with indexes.

### 1d. Create `skills/refinet-security-sentinel/references/threat-patterns.md`

Full threat pattern catalog with 10 SQL detection queries: SIWE brute force, TOTP brute force, credential stuffing, expired JWT reuse, API key abuse, endpoint sweep, multi-IP session, anonymous rate saturation, admin access outside hours, rapid key creation. Each includes severity, window, threshold, full SQL, interpretation, and response playbook.

## STEP 2 — Create cron configuration

Create `configs/security-sentinel-cron.yaml`:

```yaml
# REFINET Security Sentinel — Autonomous Defense Schedule
# Total recurring cost: $0

schedules:
  - name: auth-scan
    interval: 15m
    agent: security-sentinel
    task: "Run all anomaly detection rules against audit log. Alert admin for CRITICAL/HIGH."

  - name: rate-analysis
    interval: 1h
    agent: security-sentinel
    task: "Analyze rate limit patterns. Classify as NORMAL/TRAFFIC_SPIKE/LIKELY_ABUSE. Alert on abuse."

  - name: daily-briefing
    cron: "0 5 * * *"
    agent: security-sentinel
    task: "24h security briefing: anomalies, rates, TLS, wallets, BYOK gate. HTML email to admin."

  - name: tls-check
    cron: "0 4 * * 0"
    agent: security-sentinel
    task: "Check TLS cert expiry for all domains. Alert at 30/14/7 days. CRITICAL if expired."

  - name: gate-validation
    cron: "30 4 * * 0"
    agent: security-sentinel
    task: "Validate BYOK Security Gate returns 403 for incomplete auth. Alert on regression."

  - name: wallet-forensics
    cron: "0 5 * * 0"
    agent: security-sentinel
    task: "Analyze all SIWE wallets (7 days). Flag endpoint sweeps, multi-IP, error rates, rate abuse."
```

## STEP 3 — Create GitHub Actions workflow

Create `.github/workflows/security-sentinel.yml`:

```yaml
name: REFINET Security Sentinel — Autonomous Defense

on:
  schedule:
    - cron: '0 5 * * *'
    - cron: '0 4 * * 0'
  workflow_dispatch:
    inputs:
      task:
        description: 'Security task'
        required: false
        default: 'Full security scan with email report'

jobs:
  daily-scan:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install httpx
      - name: Run security scan
        run: python skills/refinet-security-sentinel/scripts/security_scan.py --email
        env:
          DATABASE_PATH: ${{ secrets.DATABASE_PATH }}
          REFINET_API_BASE: ${{ secrets.REFINET_API_BASE }}
          ADMIN_EMAIL: ${{ secrets.ADMIN_EMAIL }}
          SMTP_HOST: ${{ secrets.SMTP_HOST }}
          SMTP_PORT: ${{ secrets.SMTP_PORT }}
          MAIL_FROM: ${{ secrets.MAIL_FROM }}

  sentinel-task:
    if: github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - run: sudo apt-get install -y jq
      - run: pip install httpx
      - name: Run sentinel agent
        run: |
          chmod +x skills/refinet-platform-ops/scripts/run_agent.sh
          ./skills/refinet-platform-ops/scripts/run_agent.sh \
            security-sentinel "${{ github.event.inputs.task }}"
        env:
          REFINET_ROOT: ${{ github.workspace }}
          REFINET_API_BASE: ${{ secrets.REFINET_API_BASE }}
          BITNET_HOST: ${{ secrets.BITNET_HOST }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          ADMIN_EMAIL: ${{ secrets.ADMIN_EMAIL }}
          SMTP_HOST: ${{ secrets.SMTP_HOST }}
          SMTP_PORT: ${{ secrets.SMTP_PORT }}
```

## STEP 4 — Create server cron installer

Create `scripts/install_security_sentinel_cron.sh`:

```bash
#!/bin/bash
set -euo pipefail
REPO_ROOT="${REFINET_ROOT:-.}"
AGENT_SCRIPT="${REPO_ROOT}/skills/refinet-platform-ops/scripts/run_agent.sh"
SCAN_SCRIPT="${REPO_ROOT}/skills/refinet-security-sentinel/scripts/security_scan.py"
chmod +x "$AGENT_SCRIPT" 2>/dev/null || true
crontab -l 2>/dev/null | grep -v "REFINET-SECURITY" | crontab - 2>/dev/null || true
(crontab -l 2>/dev/null; cat <<CRON

# ── REFINET-SECURITY: Security Sentinel Agent ───────────────────
# Every 15 minutes — auth anomaly scan
*/15 * * * * cd ${REPO_ROOT} && python3 ${SCAN_SCRIPT} >> /var/log/refinet-security.log 2>&1 # REFINET-SECURITY

# Daily 05:00 — full security briefing email
0 5 * * * cd ${REPO_ROOT} && python3 ${SCAN_SCRIPT} --email >> /var/log/refinet-security.log 2>&1 # REFINET-SECURITY

# Weekly Sunday 04:00 — TLS cert check
0 4 * * 0 cd ${REPO_ROOT} && python3 ${SCAN_SCRIPT} --tls-only --email >> /var/log/refinet-security.log 2>&1 # REFINET-SECURITY

# Weekly Sunday 04:30 — BYOK gate validation
30 4 * * 0 cd ${REPO_ROOT} && python3 ${SCAN_SCRIPT} --gate-only >> /var/log/refinet-security.log 2>&1 # REFINET-SECURITY

# Weekly Sunday 05:00 — wallet forensics
0 5 * * 0 cd ${REPO_ROOT} && ${AGENT_SCRIPT} security-sentinel "Weekly wallet forensics and threat report" >> /var/log/refinet-security.log 2>&1 # REFINET-SECURITY
CRON
) | crontab -
echo "Security sentinel cron installed. Logs: /var/log/refinet-security.log"
crontab -l | grep "REFINET-SECURITY"
```

Mark executable: `chmod +x scripts/install_security_sentinel_cron.sh`

## STEP 5 — Update AGENTS.md

Read `AGENTS.md` and add/enhance the security-sentinel entry. Note: there is no existing `security-sentinel` agent in the registry — this is a new archetype.

```markdown

## security-sentinel

**Role**: Autonomous platform defense — auth anomaly detection, rate limit intelligence, TLS monitoring, SIWE wallet forensics, and BYOK Security Gate validation.

**Trigger sources**: Cron (15m auth scan, 1h rate analysis, daily briefing, weekly TLS/gate/forensics), webhook (auth failure spike), heartbeat.

**LLM runtime**: Zero-cost fallback chain — Claude Code CLI → Ollama → BitNet → Gemini Flash.

**Tools** (MCP gateway access):
- `admin.audit-log` — Query append-only audit log (read-only)
- `admin.stats` — Platform statistics
- `db.read.auth_logs` — Direct DB queries for anomaly detection
- `db.read.rate_limits` — Rate limit hit analysis
- `script.run.ops.*` — Operational script execution (certbot, etc.)
- `smtp.send` — Email admin alerts and briefings

**Delegation policy**: `auto` — accepts from platform-ops and orchestrator. Can delegate to platform-ops for infrastructure actions. Max depth: 3.

**Core principle**: The sentinel observes and reports — it never blocks, bans, or modifies. All enforcement requires explicit admin approval.

**Detection rules**: SIWE brute force, TOTP brute force, credential stuffing, expired JWT reuse, API key abuse, rapid key creation, endpoint sweeping, multi-IP sessions, admin access anomalies, anonymous rate saturation.

**Email alert categories**: AUTH_ANOMALY, RATE_ABUSE, TLS_EXPIRY, WALLET_FLAG, GATE_FAIL, BRIEFING.

**Key files**:
- `skills/refinet-security-sentinel/SKILL.md` — Full operational manual
- `skills/refinet-security-sentinel/scripts/security_scan.py` — Defense scanner
- `skills/refinet-security-sentinel/references/auth-api.md` — Auth API reference
- `skills/refinet-security-sentinel/references/threat-patterns.md` — Threat catalog with SQL queries
- `configs/security-sentinel-cron.yaml` — Cron schedule
- `.github/workflows/security-sentinel.yml` — GitHub Actions runner
```

## STEP 6 — Wire into HEARTBEAT.md

Append to `HEARTBEAT.md`:

```markdown

### Security Sentinel Integration

| Interval | Agent | Task |
|---|---|---|
| 15m | security-sentinel | Auth anomaly detection scan |
| 1h | security-sentinel | Rate limit pattern analysis |
| Daily 05:00 | security-sentinel | Full security briefing email |
| Weekly Sun 04:00 | security-sentinel | TLS certificate check |
| Weekly Sun 04:30 | security-sentinel | BYOK gate validation |
| Weekly Sun 05:00 | security-sentinel | SIWE wallet forensics |
```

## STEP 7 — Create setup documentation

Create `docs/SECURITY_SENTINEL_SETUP.md`:

```markdown
# Security Sentinel Setup Guide

## What It Does

The security-sentinel is the platform's autonomous defense system:
- Scans the append-only audit log every 15 minutes for 6 attack patterns
- Classifies rate limit patterns as normal traffic, legitimate spikes, or deliberate abuse
- Monitors TLS certificate expiry and alerts at 30/14/7 days
- Conducts wallet-level forensics on all SIWE-authenticated sessions
- Validates the BYOK Security Gate blocks incomplete auth combinations
- Sends daily security briefing emails to admin

The sentinel observes and reports — it never blocks, bans, or modifies.

## Prerequisites

1. `refinet-platform-ops` skill installed (provides run_agent.sh)
2. Audit log table exists in public.db
3. SMTP bridge configured for admin alerts

## Testing Locally

\`\`\`bash
# Full security scan
python skills/refinet-security-sentinel/scripts/security_scan.py

# Full scan + email
python skills/refinet-security-sentinel/scripts/security_scan.py --email

# TLS check only
python skills/refinet-security-sentinel/scripts/security_scan.py --tls-only

# BYOK gate validation only
python skills/refinet-security-sentinel/scripts/security_scan.py --gate-only

# Wallet forensics on specific address
python skills/refinet-security-sentinel/scripts/security_scan.py --wallet 0xabc123...
\`\`\`

## Cost Breakdown

| Component | Monthly Cost |
|---|---|
| SQLite audit log queries | $0 (local) |
| TLS certificate checks | $0 (stdlib ssl) |
| BYOK gate validation | $0 (HTTP to localhost) |
| GitHub Actions | $0 (shared pool) |
| Self-hosted SMTP | $0 (Haraka) |
| **Total** | **$0/month** |

## Complete Autonomous Agent Pipeline

With all 4 skills installed, the platform runs fully autonomously:

| Agent | Domain | Key Schedule |
|---|---|---|
| platform-ops | Infrastructure health | 60s heartbeat, daily summary |
| knowledge-curator | RAG/CAG intelligence | 30m ingestion, 6h orphan repair |
| contract-watcher | On-chain security | 5m events, 15m ABI scan |
| security-sentinel | Platform defense | 15m auth scan, daily briefing |

Total cost: $0/month. All open source. All sovereign.
```

## STEP 8 — Verify and report

After completing all steps, verify:

1. `ls skills/refinet-security-sentinel/` shows: SKILL.md, scripts/, references/
2. `ls skills/refinet-security-sentinel/scripts/` shows: security_scan.py
3. `ls skills/refinet-security-sentinel/references/` shows: auth-api.md, threat-patterns.md
4. `cat configs/security-sentinel-cron.yaml` exists with 6 schedule entries
5. `cat .github/workflows/security-sentinel.yml` exists with 2 jobs
6. `cat scripts/install_security_sentinel_cron.sh` exists and is executable
7. `cat docs/SECURITY_SENTINEL_SETUP.md` exists with complete agent pipeline table
8. `AGENTS.md` has new security-sentinel entry
9. `HEARTBEAT.md` has Security Sentinel Integration table
10. Platform-ops `run_agent.sh` is reused — not duplicated

Print file summary with line counts. Confirm: ALL 4 AUTONOMOUS AGENT SKILLS ARE NOW COMPLETE.

| # | Skill | Domain |
|---|---|---|
| 1 | platform-ops | Infrastructure |
| 2 | knowledge-curator | Intelligence |
| 3 | contract-watcher | Blockchain |
| 4 | security-sentinel | Defense |

The REFINET Cloud autonomous agent pipeline is fully operational at $0/month.
```

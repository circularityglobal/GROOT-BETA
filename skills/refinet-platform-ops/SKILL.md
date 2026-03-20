---
name: refinet-platform-ops
description: >
  REFINET Cloud platform operations skill for autonomous oversight, monitoring,
  and administration of the GROOT-BETA sovereign AI platform. Use this skill whenever
  the user wants to: monitor REFINET Cloud health, audit GROOT agents, manage the
  heartbeat system, send admin email notifications about platform changes, deploy
  updates to the REFINET infrastructure, manage the agent engine lifecycle, check
  BitNet inference status, review security audit logs, manage the smart contract
  registry, run platform maintenance scripts, orchestrate autonomous agent pipelines,
  or build fully automated agentic workflows on REFINET Cloud. Triggers on phrases
  like "REFINET ops", "GROOT status", "platform health", "agent monitoring",
  "heartbeat check", "admin email", "platform oversight", "REFINET deploy",
  "GROOT agents", "autonomous pipeline", "agentic flow REFINET", "platform-ops agent",
  "contract registry audit", "BitNet health", "REFINET maintenance", "agent engine",
  "sovereign platform ops", "GROOT brain", "MCP gateway status", "chain listener",
  "REFINET admin alert", or any request to operate, monitor, maintain, or automate
  the GROOT-BETA / REFINET Cloud platform. Also use when the user mentions
  "circularityglobal", "app.refinet.io", "api.refinet.io", or "CIFI platform ops".
---

# REFINET Cloud Platform Operations Skill

This skill gives Claude everything needed to:
1. Autonomously oversee all REFINET Cloud subsystems (inference, agents, registry, messaging, chain listener, knowledge base, MCP gateway)
2. Send structured admin email notifications for platform changes, health alerts, and agent activity summaries
3. Orchestrate fully automated, zero-cost agentic pipelines using only open-source tooling
4. Run the 6-phase cognitive loop agents against the live platform via Claude Code CLI

---

## Part 1 — Platform Architecture Map

Before operating on the platform, internalize this map. Every ops action maps to a subsystem.

### 1.1 REFINET Cloud Subsystem Registry

| Subsystem | API Base | Health Endpoint | What It Does |
|---|---|---|---|
| BitNet Inference | `/v1/chat/completions` | `GET /health` | CPU-native LLM inference (BitNet b1.58 2B4T) |
| Agent Engine | `/agents/*` | `GET /health` | 6-phase cognitive loop, SOUL.md identity, 4-tier memory |
| Smart Contract Registry | `/registry/*` | via `/health` | ABI upload, parsing, SDK generation, explorer |
| GROOT Brain | `/repo/*` | via `/health` | Per-user contract namespace, ABI parsing |
| Knowledge Base | `/knowledge/*` | via `/health` | RAG + CAG context injection, semantic search |
| Messaging | `/messages/*` | via `/health` | Wallet-to-wallet encrypted messaging, SMTP bridge |
| Chain Listener | `/chain/*` | via `/health` | On-chain event monitoring, webhook triggers |
| DApp Factory | `/dapp/*` | via `/health` | Template-based DApp assembly |
| App Store | `/app-store/*` | via `/health` | Publish and discover DApps, agents, tools |
| Device Connectivity | `/devices/*` | via `/health` | IoT/PLC/DLT telemetry ingestion |
| MCP Gateway | `/mcp/*` | via `/health` | 6-protocol gateway (REST, GraphQL, gRPC, SOAP, WS, Webhooks) |
| Task Scheduler | internal | via `/health` | Cron-like scheduled execution, 23 operational scripts |
| Auth System | `/auth/*` | via `/health` | SIWE + Argon2id + TOTP, JWT scopes |

### 1.2 Infrastructure Constraints

These are hard constraints — the platform runs entirely on Oracle Cloud Always Free tier:

- **Server**: ARM A1 Flex (4 OCPUs, 24GB RAM, 200GB storage)
- **Cost**: Zero recurring. No exceptions.
- **Database**: SQLite WAL mode, dual-database (public.db + internal.db)
- **TLS**: Let's Encrypt via Certbot
- **Email**: Self-hosted SMTP bridge on port 8025 (Haraka/Nodemailer)
- **DNS**: Sovereign — platform owns all DNS records
- **License**: AGPL-3.0

### 1.3 The Heartbeat Protocol

The platform has a 60-second pulse cycle. On each heartbeat:

1. Check webhook queue for unprocessed events
2. Check cron schedule for due jobs
3. Check chain listener for new on-chain events
4. Check messenger inboxes for unread commands
5. Check working memory for pending tasks from previous runs

**Escalation rules**:
- Actionable data → route to Trigger Router
- All checks empty → log heartbeat, sleep
- 3 consecutive heartbeat failures → alert admin via webhook
- Inference latency > 30s → warning
- DB query latency > 5s → warning

---

## Part 2 — Admin Email Notification System

The platform uses self-hosted SMTP (no third-party providers). All admin alerts route through the REFINET SMTP bridge.

### 2.1 Email Configuration

```python
# Environment variables (already in .env.example)
ADMIN_EMAIL=admin@refinet.io          # Primary admin recipient
SMTP_HOST=127.0.0.1                   # Local Haraka instance
SMTP_PORT=8025                        # REFINET SMTP bridge port
MAIL_FROM=groot@refinet.io            # Sender identity
```

### 2.2 Admin Alert Categories

When building platform ops scripts or agents, use these categories for email subject lines:

| Category | Subject Prefix | When |
|---|---|---|
| HEALTH | `[REFINET HEALTH]` | Heartbeat failures, subsystem down, latency warnings |
| SECURITY | `[REFINET SECURITY]` | Auth anomalies, failed SIWE attempts, rate limit spikes |
| AGENT | `[REFINET AGENT]` | Agent lifecycle events, delegation chains, memory overflow |
| DEPLOY | `[REFINET DEPLOY]` | Code pushes, migration runs, config changes |
| CHAIN | `[REFINET CHAIN]` | On-chain events, contract interactions, bridge activity |
| REGISTRY | `[REFINET REGISTRY]` | New contracts, ABI uploads, dangerous function flags |
| KNOWLEDGE | `[REFINET KNOWLEDGE]` | RAG index updates, new document ingestion, CAG changes |
| MAINTENANCE | `[REFINET MAINTENANCE]` | Scheduled tasks, cleanup runs, backup completion |

### 2.3 Email Sending Pattern (Python — FastAPI)

All ops scripts and agents should use this pattern to send admin alerts:

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime, timezone

def send_admin_alert(
    category: str,
    subject: str,
    body_html: str,
    body_text: str | None = None,
    priority: str = "normal"  # "low", "normal", "high", "critical"
):
    """Send alert to admin via self-hosted SMTP. Never throws — logs on failure."""
    admin_email = os.getenv("ADMIN_EMAIL")
    if not admin_email:
        print("[ops] ADMIN_EMAIL not set — skipping alert")
        return

    msg = MIMEMultipart("alternative")
    msg["From"] = os.getenv("MAIL_FROM", "groot@refinet.io")
    msg["To"] = admin_email
    msg["Subject"] = f"[REFINET {category.upper()}] {subject}"
    msg["X-Priority"] = {"low": "5", "normal": "3", "high": "2", "critical": "1"}[priority]
    msg["X-REFINET-Category"] = category
    msg["X-REFINET-Timestamp"] = datetime.now(timezone.utc).isoformat()

    if body_text:
        msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(
            os.getenv("SMTP_HOST", "127.0.0.1"),
            int(os.getenv("SMTP_PORT", "8025"))
        ) as server:
            server.send_message(msg)
            print(f"[ops] Alert sent: {category} — {subject}")
    except Exception as e:
        print(f"[ops] Email send failed: {e}")
```

### 2.4 Structured Alert Templates

For HTML email bodies, use this minimal template that renders in all clients:

```html
<div style="font-family: -apple-system, sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="background: #1a1a2e; color: #e0e0e0; padding: 16px 20px; border-radius: 8px 8px 0 0;">
    <h2 style="margin: 0; font-size: 18px;">🌱 REFINET Cloud — {CATEGORY}</h2>
    <p style="margin: 4px 0 0; font-size: 12px; color: #888;">{TIMESTAMP}</p>
  </div>
  <div style="background: #16213e; color: #e0e0e0; padding: 20px; border-radius: 0 0 8px 8px;">
    <h3 style="margin: 0 0 12px; color: #00d4aa;">{SUBJECT}</h3>
    {BODY_CONTENT}
    <hr style="border: 1px solid #333; margin: 16px 0;">
    <p style="font-size: 11px; color: #666;">
      Sent by GROOT Platform Ops Agent · <a href="https://app.refinet.io" style="color: #00d4aa;">app.refinet.io</a>
    </p>
  </div>
</div>
```

---

## Part 3 — Autonomous Agentic Pipeline Architecture

This is the core value: running Claude-powered agents for free, fully operated by open-source technology through REFINET Cloud.

### 3.1 The Zero-Cost Agent Execution Stack

The entire pipeline runs without any paid API calls:

```
┌─────────────────────────────────────────────────────────┐
│                    TRIGGER LAYER                         │
│  Heartbeat (60s) │ Cron │ Webhook │ Chain │ Messenger   │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│                  ORCHESTRATION LAYER                     │
│  Claude Code CLI (claude -p)  ←  FREE, unlimited local  │
│  ↓ falls back to ↓                                      │
│  Ollama (phi3-mini / llama3)  ←  FREE, local CPU/GPU    │
│  ↓ falls back to ↓                                      │
│  BitNet b1.58 2B4T            ←  FREE, CPU-native ARM   │
│  ↓ falls back to ↓                                      │
│  Gemini Flash (free tier)     ←  FREE, 15 RPM           │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│                   AGENT ENGINE                           │
│  PERCEIVE → PLAN → ACT → OBSERVE → REFLECT → STORE     │
│                                                          │
│  Identity:  SOUL.md (persistent across runs)             │
│  Memory:    Working → Episodic → Semantic → Procedural   │
│  Tools:     MCP Gateway (glob-pattern permissions)       │
│  Safety:    SAFETY.md hard constraints injected always   │
│  Audit:     JSONL episodic trail + DB storage            │
└─────────────┬───────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│                   OUTPUT ROUTING                         │
│  DB │ HTTP Response │ Memory │ Agent Chain │ Webhook     │
│  ↓                                                       │
│  Admin Email (self-hosted SMTP)                          │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Claude Code CLI as the Primary Free Agent Runtime

Claude Code CLI (`claude -p`) is the highest-quality free agent runtime available. It runs locally, has no rate limits for local use, and can execute the full 6-phase cognitive loop.

**How to wire it into REFINET's agent engine:**

```bash
#!/bin/bash
# scripts/run_agent_pipeline.sh
# Executes an agent task through Claude Code CLI with REFINET context injection

AGENT_NAME="${1:-platform-ops}"
TASK="${2:-Run heartbeat check and report status}"
SOUL_FILE="SOUL.md"
SAFETY_FILE="SAFETY.md"
MEMORY_DIR="memory/"

# Assemble context (7-layer injection stack)
CONTEXT=$(cat <<EOF
[SOUL] $(cat $SOUL_FILE)
[SAFETY] $(cat $SAFETY_FILE)
[AGENT] $(cat agents/${AGENT_NAME}.yaml 2>/dev/null || echo "default agent config")
[MEMORY] $(cat ${MEMORY_DIR}/working/latest.json 2>/dev/null || echo "{}")
[TASK] ${TASK}
EOF
)

# Execute via Claude Code CLI (free, unlimited)
RESULT=$(claude -p "$CONTEXT" 2>/dev/null)

# If Claude Code unavailable, fall back to Ollama
if [ $? -ne 0 ]; then
    RESULT=$(curl -s http://localhost:11434/api/generate \
        -d "{\"model\": \"phi3:mini\", \"prompt\": \"$CONTEXT\", \"stream\": false}" \
        | jq -r '.response')
fi

# If Ollama unavailable, fall back to BitNet
if [ -z "$RESULT" ] || [ "$RESULT" = "null" ]; then
    RESULT=$(curl -s http://localhost:8080/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d "{\"model\": \"bitnet-b1.58-2b\", \"messages\": [{\"role\": \"user\", \"content\": \"$CONTEXT\"}]}" \
        | jq -r '.choices[0].message.content')
fi

# Store result in episodic memory
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "{\"timestamp\": \"$TIMESTAMP\", \"agent\": \"$AGENT_NAME\", \"task\": \"$TASK\", \"result\": $(echo "$RESULT" | jq -Rs .)}" \
    >> "${MEMORY_DIR}/episodic/${AGENT_NAME}.jsonl"

# Output result
echo "$RESULT"
```

### 3.3 The 10 Built-In Agent Archetypes

REFINET ships with these agents. The platform-ops skill can invoke any of them:

| Archetype | Purpose | Trigger Source |
|---|---|---|
| `groot-chat` | Primary chat assistant with RAG+CAG | User message |
| `contract-analyst` | ABI analysis, dangerous function detection | Registry upload |
| `knowledge-curator` | Document ingestion, embedding, index maintenance | Knowledge upload |
| `platform-ops` | **This agent** — health monitoring, admin alerts, maintenance | Heartbeat, cron |
| `dapp-builder` | Template assembly, contract wiring | User request |
| `device-monitor` | IoT telemetry analysis, anomaly detection | Device telemetry |
| `contract-watcher` | On-chain event monitoring, alert generation | Chain listener |
| `onboarding` | New user setup, wallet connection guidance | First auth |
| `maintenance` | DB cleanup, memory pruning, log rotation | Cron schedule |
| `orchestrator` | Agent-to-agent delegation, pipeline coordination | Any agent |

### 3.4 Cron-Driven Autonomous Ops Pipeline

The recommended pipeline for fully autonomous oversight:

```yaml
# configs/platform-ops-cron.yaml
schedules:
  # Every 60 seconds — heartbeat
  - name: heartbeat
    interval: 60s
    agent: platform-ops
    task: "Run health check on all subsystems. If any fail, send HEALTH alert."

  # Every 5 minutes — inference quality check
  - name: inference-check
    interval: 5m
    agent: platform-ops
    task: "Send test prompt to BitNet. Measure latency. Alert if >30s or failure."

  # Every 15 minutes — security audit
  - name: security-audit
    interval: 15m
    agent: platform-ops
    task: "Check auth logs for anomalies. Review rate limit hits. Alert on spikes."

  # Every hour — agent memory cleanup
  - name: memory-cleanup
    interval: 1h
    agent: maintenance
    task: "Prune expired working memory. Compact episodic logs older than 7 days."

  # Every 6 hours — knowledge base integrity
  - name: knowledge-integrity
    interval: 6h
    agent: knowledge-curator
    task: "Verify embedding index consistency. Re-embed any orphaned documents."

  # Daily at 06:00 UTC — platform summary email
  - name: daily-summary
    interval: "0 6 * * *"
    agent: platform-ops
    task: "Compile 24h platform summary: requests served, agents run, contracts added, errors. Email admin."

  # Weekly — full audit
  - name: weekly-audit
    interval: "0 6 * * 1"
    agent: platform-ops
    task: "Full platform audit: DB size, memory usage, API key expiry, certificate expiry, chain listener health. Email detailed report."
```

---

## Part 4 — Platform Health Check Implementation

### 4.1 Comprehensive Health Check Script

When the user asks to check platform health or implement monitoring, generate this:

```python
#!/usr/bin/env python3
"""REFINET Cloud Platform Health Check — runs all subsystem checks and emails admin."""

import httpx
import asyncio
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

API_BASE = os.getenv("REFINET_API_BASE", "http://localhost:8000")
BITNET_HOST = os.getenv("BITNET_HOST", "http://localhost:8080")

async def check_health():
    """Run all health checks and return structured report."""
    results = {}
    async with httpx.AsyncClient(timeout=10.0) as client:

        # 1. Main API health
        try:
            r = await client.get(f"{API_BASE}/health")
            results["api"] = {"ok": r.status_code == 200, "latency_ms": r.elapsed.total_seconds() * 1000}
        except Exception as e:
            results["api"] = {"ok": False, "error": str(e)}

        # 2. BitNet inference
        try:
            r = await client.post(f"{BITNET_HOST}/v1/chat/completions", json={
                "model": "bitnet-b1.58-2b",
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 5
            })
            results["bitnet"] = {"ok": r.status_code == 200, "latency_ms": r.elapsed.total_seconds() * 1000}
        except Exception as e:
            results["bitnet"] = {"ok": False, "error": str(e)}

        # 3. Database connectivity
        try:
            db_path = os.getenv("DATABASE_PATH", "public.db")
            conn = sqlite3.connect(db_path)
            conn.execute("SELECT 1")
            conn.close()
            results["database"] = {"ok": True}
        except Exception as e:
            results["database"] = {"ok": False, "error": str(e)}

        # 4. SMTP bridge
        try:
            import smtplib
            with smtplib.SMTP(os.getenv("SMTP_HOST", "127.0.0.1"), int(os.getenv("SMTP_PORT", "8025"))) as s:
                s.noop()
            results["smtp"] = {"ok": True}
        except Exception as e:
            results["smtp"] = {"ok": False, "error": str(e)}

    # 5. Disk usage
    import shutil
    total, used, free = shutil.disk_usage("/")
    results["disk"] = {
        "ok": (free / total) > 0.1,  # Alert if <10% free
        "total_gb": round(total / (1024**3), 1),
        "used_gb": round(used / (1024**3), 1),
        "free_gb": round(free / (1024**3), 1),
        "used_pct": round((used / total) * 100, 1)
    }

    # 6. Memory usage
    try:
        with open("/proc/meminfo") as f:
            meminfo = dict(line.split(":")[:2] for line in f.readlines() if ":" in line)
        total_mem = int(meminfo.get("MemTotal", "0 kB").strip().split()[0])
        free_mem = int(meminfo.get("MemAvailable", "0 kB").strip().split()[0])
        results["memory"] = {
            "ok": (free_mem / total_mem) > 0.15 if total_mem > 0 else False,
            "total_mb": round(total_mem / 1024),
            "available_mb": round(free_mem / 1024),
            "used_pct": round((1 - free_mem / total_mem) * 100, 1) if total_mem > 0 else 0
        }
    except Exception:
        results["memory"] = {"ok": True, "note": "Non-Linux — skipped"}

    return results


def format_health_report(results: dict) -> tuple[str, str]:
    """Return (html_body, text_body) for the admin email."""
    all_ok = all(r.get("ok", False) for r in results.values())
    status_emoji = "✅" if all_ok else "🚨"

    rows = ""
    for subsystem, data in results.items():
        ok = data.get("ok", False)
        icon = "✅" if ok else "❌"
        detail = ""
        if "latency_ms" in data:
            detail = f"{data['latency_ms']:.0f}ms"
        elif "error" in data:
            detail = f"<span style='color:#ff4444'>{data['error'][:80]}</span>"
        elif "used_pct" in data:
            detail = f"{data['used_pct']}% used"
        rows += f"<tr><td>{icon}</td><td><b>{subsystem}</b></td><td>{detail}</td></tr>"

    html = f"""
    <p>{status_emoji} <b>{'All systems operational' if all_ok else 'Issues detected'}</b></p>
    <table style="width:100%; border-collapse:collapse;">
      <tr style="border-bottom:1px solid #333;"><th>Status</th><th>Subsystem</th><th>Detail</th></tr>
      {rows}
    </table>
    """
    text = json.dumps(results, indent=2)
    return html, text
```

---

## Part 5 — Fully Autonomous Agent Deployment Strategies

### 5.1 Strategy Matrix — Running Agents for Free

| Strategy | Runtime | Cost | Quality | Best For |
|---|---|---|---|---|
| **Claude Code CLI** | `claude -p` locally | $0 | Highest (Opus/Sonnet) | Complex reasoning, code generation, multi-step ops |
| **Ollama Local** | ollama serve + phi3/llama3 | $0 | Good for structured tasks | Template filling, log parsing, status reports |
| **BitNet Native** | bitnet.cpp on ARM | $0 | Basic chat, RAG-grounded answers | User-facing chat, simple Q&A |
| **Gemini Free** | Google AI Studio free tier | $0 (15 RPM) | Good | Fallback, web-grounded answers |
| **GitHub Actions** | CI/CD pipeline | $0 (2000 min/month) | Any model via CLI | Scheduled audits, weekly reports |
| **Cron + CLI** | Server crontab | $0 | Any local model | Heartbeat, health checks, cleanup |

### 5.2 The Recommended Stack (Maximum Autonomy, Zero Cost)

```
PRIMARY:   Claude Code CLI (`claude -p`)
           ↳ Runs locally on your Mac or on the Oracle ARM server
           ↳ Full tool use, file I/O, bash, web search
           ↳ Highest quality reasoning for ops decisions

SECONDARY: Ollama (phi3-mini or llama3.2:3b)
           ↳ Runs on Oracle ARM (24GB RAM = fits 7B+ models)
           ↳ Good for structured output, log parsing, summarization
           ↳ OpenAI-compatible API at localhost:11434

TERTIARY:  BitNet b1.58 2B4T (already running on REFINET)
           ↳ CPU-native, no GPU, always available
           ↳ RAG+CAG grounded — better than raw model for platform knowledge
           ↳ The "always-on brain" for user-facing queries

FALLBACK:  Gemini 2.0 Flash (free tier via Universal Model Gateway)
           ↳ 15 requests/minute, web-grounded
           ↳ Good for external research tasks
```

### 5.3 GitHub Actions as Free Agent Scheduler

For tasks that don't need to run on the server itself, use GitHub Actions:

```yaml
# .github/workflows/platform-ops.yml
name: REFINET Platform Ops
on:
  schedule:
    - cron: '0 6 * * *'    # Daily at 06:00 UTC
    - cron: '0 6 * * 1'    # Weekly on Monday
  workflow_dispatch:         # Manual trigger

jobs:
  daily-health:
    if: github.event.schedule == '0 6 * * *' || github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run health check
        run: |
          pip install httpx
          python scripts/health_check.py
        env:
          REFINET_API_BASE: https://api.refinet.io
          ADMIN_EMAIL: ${{ secrets.ADMIN_EMAIL }}
          SMTP_HOST: ${{ secrets.SMTP_HOST }}

  weekly-audit:
    if: github.event.schedule == '0 6 * * 1'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run full audit
        run: python scripts/full_audit.py
        env:
          REFINET_API_BASE: https://api.refinet.io
          ADMIN_EMAIL: ${{ secrets.ADMIN_EMAIL }}
```

---

## Part 6 — Operating Procedures

### 6.1 When User Asks to Check Platform Status

1. Read `HEARTBEAT.md` for current pulse config
2. Run health check against all subsystems (Part 4)
3. Compare against alert thresholds
4. If issues found → format alert email and send via SMTP
5. If all clear → log healthy heartbeat

### 6.2 When User Asks to Deploy Updates

1. Run `scripts/pre_deploy_check.py` (DB backup, health baseline)
2. Pull latest from `main` branch
3. Run Alembic migrations: `alembic upgrade head`
4. Restart FastAPI via `systemctl restart refinet` or Docker
5. Run post-deploy health check
6. Email admin with deploy summary (what changed, migration status, health delta)

### 6.3 When User Asks to Set Up Autonomous Agent Pipeline

1. Verify Claude Code CLI is installed (`claude --version`)
2. Verify Ollama is available (`curl localhost:11434/api/tags`)
3. Verify BitNet is running (`curl localhost:8080/health`)
4. Install cron entries from `configs/platform-ops-cron.yaml`
5. Run initial health check to establish baseline
6. Email admin confirming pipeline activation

### 6.4 When User Asks to Audit Agents

1. List all registered agents via `GET /agents`
2. For each agent, check last heartbeat, memory usage, task count
3. Check JSONL episodic trail for anomalies (error spikes, long run times)
4. Check delegation chains (max depth: 3 per SAFETY.md)
5. Compile audit report and email admin

---

## Part 7 — Safety Constraints (Always Enforced)

These are inherited from SAFETY.md and cannot be overridden:

- Never expose private keys, seed phrases, Shamir shares, or encryption keys
- Never execute financial transactions without explicit user confirmation
- Never bypass authentication or escalate privileges
- Never spawn unbounded recursive agent delegation chains (max depth: 3)
- Never disable security features (rate limiting, auth, audit logging)
- Always log all tool calls to episodic memory
- Always verify user identity before acting on their behalf
- Always cite knowledge base sources when using RAG context
- Append-only audit log — no delete or update routes

---

## Part 8 — Reference Files

Read these when implementing specific subsystem operations:

- `references/api-endpoints.md` — Complete 210+ endpoint reference with auth requirements
- `references/agent-engine.md` — Agent Engine architecture: SOUL identity, memory tiers, cognitive loop, MCP tool dispatch
- `references/email-templates.md` — HTML email templates for each alert category

For the agent-os folder standard and general agentic architecture patterns, consult the `agent-os` skill.
For Electron desktop agent deployment, consult the `electron-agent-os` skill.
For encrypted secrets storage, consult the `encrypted-secrets-db` skill.
For self-hosted SMTP implementation details, consult the `smtp-self-hosted` skill.

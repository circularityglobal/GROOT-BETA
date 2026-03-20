# HEARTBEAT.md — System Heartbeat Protocol

The heartbeat protocol defines how REFINET Cloud monitors its own health, schedules maintenance, and alerts on failures.

---

## Health Check Architecture

```
TaskScheduler (10s tick)
  └── health_monitor (every 60s)
        ├── BitNet inference sidecar → http://127.0.0.1:8080/health
        ├── Public database → SELECT 1
        ├── Internal database → SELECT 1
        └── SMTP bridge → connection test (if enabled)
              ↓
        HealthCheckLog (internal.db)
              ↓
        Monitor alerts (if failures detected)
```

## Scheduled Tasks (Default)

| Task | Interval | Handler | Purpose |
|------|----------|---------|---------|
| `health_monitor` | 60s | `api.services.scheduler.health_check_handler` | Database + inference + SMTP health check |
| `p2p_cleanup` | 60s | `api.services.scheduler.p2p_cleanup_handler` | Remove stale P2P peers (>5 min inactive) |
| `auth_cleanup` | 3600s | `api.services.scheduler.auth_cleanup_handler` | Expire SIWE nonces + refresh tokens |
| `agent_memory_cleanup` | 300s | `api.services.scheduler.memory_cleanup_handler` | Remove expired agent working memory |

All tasks are managed via the `ScheduledTask` table in `internal.db` and run by the `TaskScheduler` singleton.

## Health Check Details

### Inference Sidecar
- **Target:** `http://127.0.0.1:8080/health` (BitNet llama-server)
- **Timeout:** 5 seconds
- **Logged:** `inference_ok` (boolean) + `inference_latency_ms` (integer)
- **Alert threshold:** 3 consecutive failures

### Database Connectivity
- **Method:** `SELECT 1` on both public and internal SQLite databases
- **Logged:** `database_ok` (boolean)
- **Impact:** If database fails, all API endpoints return 500

### SMTP Bridge
- **Target:** localhost:8025 (if `smtp_enabled` is true)
- **Logged:** `smtp_ok` (boolean)
- **Non-critical:** SMTP failure doesn't affect core operations

## Uptime Tracking

Health check results are stored in `health_check_logs` (internal.db):

```sql
CREATE TABLE health_check_logs (
    id TEXT PRIMARY KEY,
    timestamp DATETIME,
    inference_ok BOOLEAN,
    inference_latency_ms INTEGER,
    database_ok BOOLEAN,
    smtp_ok BOOLEAN,
    notes TEXT
);
```

Uptime is computed via `GET /admin/uptime`:
- **Last 24 hours:** % of checks where all services were OK
- **Last 7 days:** Same calculation over wider window
- **Last 30 days:** Long-term reliability metric

## Agent Heartbeat

Agents report health via `POST /agents/{agent_id}/heartbeat`:

```json
{
    "version": "1.2.0",
    "status": "running"
}
```

This updates `AgentRegistration.last_connected_at`. Agents that haven't sent a heartbeat in 5+ minutes are considered stale (not automatically deactivated — just flagged).

## Alert Thresholds

| Condition | Severity | Action |
|-----------|----------|--------|
| Inference sidecar down for 3+ checks | HIGH | Log warning, set `inference_ok=false` |
| Database connection failure | CRITICAL | Log error, all endpoints affected |
| SMTP bridge down | LOW | Log warning, email aliases non-functional |
| Agent heartbeat stale >1 hour | INFO | Logged for admin review |
| Scheduled task fails 3+ times | MEDIUM | `last_error` updated, task remains enabled |

## Admin Management

Scheduled tasks can be managed via admin API:

```
GET    /admin/scheduled-tasks              — List all tasks
POST   /admin/scheduled-tasks              — Create new task
PUT    /admin/scheduled-tasks/{id}         — Enable/disable or change schedule
DELETE /admin/scheduled-tasks/{id}         — Remove task
POST   /admin/scheduled-tasks/{id}/run     — Force immediate execution
```

Health status is available via:

```
GET    /admin/uptime                       — Uptime percentages (24h/7d/30d)
GET    /admin/usage/summary?period=week    — Usage aggregation with token counts
GET    /admin/stats                        — Platform-wide counts
```

---

## Platform Ops Skill — Extended Monitoring

The `skills/refinet-platform-ops/` skill extends the heartbeat protocol with autonomous monitoring capabilities:

### Comprehensive Health Checker (`health_check.py`)

Tests 6 subsystems: API health, BitNet inference (latency + status), database connectivity, SMTP bridge, disk usage (alert if <10% free), and memory usage (alert if <15% available). Sends formatted HTML email alerts to admin when issues are detected.

```bash
python3 skills/refinet-platform-ops/scripts/health_check.py                  # Print results
python3 skills/refinet-platform-ops/scripts/health_check.py --email          # Email on failure
python3 skills/refinet-platform-ops/scripts/health_check.py --email --always # Always email
```

### Zero-Cost Agent Pipeline (`run_agent.sh`)

Executes agent tasks through a 4-tier LLM fallback chain (all free):
1. Claude Code CLI (`claude -p`)
2. Ollama (phi3-mini / llama3)
3. BitNet b1.58 2B4T
4. Gemini Flash (free tier, 15 RPM)

Results are written to `memory/episodic/{agent_name}.jsonl` as append-only JSONL.

### Admin Email Alert Categories

**Platform Ops:**

| Category | Subject Prefix | When |
|---|---|---|
| HEALTH | `[REFINET HEALTH]` | Heartbeat failures, subsystem down, latency warnings |
| SECURITY | `[REFINET SECURITY]` | Auth anomalies, failed SIWE attempts, rate limit spikes |
| AGENT | `[REFINET AGENT]` | Agent lifecycle events, delegation chains, memory overflow |
| DEPLOY | `[REFINET DEPLOY]` | Code pushes, migration runs, config changes |
| CHAIN | `[REFINET CHAIN]` | On-chain events, contract interactions |
| REGISTRY | `[REFINET REGISTRY]` | New contracts, ABI uploads, dangerous function flags |
| KNOWLEDGE | `[REFINET KNOWLEDGE]` | RAG index updates, document ingestion |
| MAINTENANCE | `[REFINET MAINTENANCE]` | Scheduled tasks, cleanup runs, backup completion |

**Knowledge Curator:**

| Category | When |
|---|---|
| INGESTION / INGESTION_FAIL | New document processed or ingestion failed |
| ORPHAN | Orphaned documents detected and re-embedded |
| PRUNE | Stale chunks pruned from vector index |
| CAG_SYNC | New ABIs synced to CAG index |
| DRIFT | Embedding quality below threshold |
| DIGEST | Daily knowledge base activity digest |

**Contract Watcher:**

| Category | When |
|---|---|
| ABI_SECURITY | Dangerous pattern found in uploaded ABI |
| EVENT_ANOMALY | Anomalous on-chain event detected |
| ACTIVITY_ALERT | Contract activity anomaly (tx spike, balance change) |
| BRIDGE_ALERT | Unmatched bridge deposit or correlation failure |
| WEEKLY_REPORT | Weekly chain intelligence digest |

### Recommended Cron Schedule (All 3 Agents)

| Interval | Agent | Task |
|---|---|---|
| 60s | platform-ops | Heartbeat health check |
| 5m | platform-ops / contract-watcher | Inference check / chain event processing |
| 15m | platform-ops / contract-watcher | Security audit / ABI security scan |
| 30m | knowledge-curator | Pending document ingestion check |
| 1h | maintenance | Agent memory cleanup |
| 4h | contract-watcher | Watched contract activity check |
| 6h | knowledge-curator | Orphan repair + CAG sync |
| 12h | contract-watcher | Cross-chain bridge correlation |
| Daily 05:30 | knowledge-curator | Embedding quality benchmark |
| Daily 06:00 | platform-ops / knowledge-curator | Platform summary + knowledge digest |
| Weekly Monday | platform-ops / contract-watcher | Platform audit + chain intelligence report |

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

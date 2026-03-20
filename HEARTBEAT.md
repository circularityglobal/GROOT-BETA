# HEARTBEAT.md — System Pulse Configuration

## Pulse Interval
60 seconds (configurable in configs/default.yaml)

## On Each Pulse
1. Check webhook queue for unprocessed events
2. Check cron schedule for due jobs
3. Check on-chain listener for new events
4. Check messenger inboxes for unread commands
5. Check memory/working/ for pending tasks from previous runs

## Escalation
If any check returns actionable data → route to Trigger Router
If all checks return empty → log heartbeat, sleep until next pulse

## Health Checks
- BitNet inference server: HTTP GET to BITNET_HOST
- Database connectivity: SQLAlchemy session test
- SMTP bridge: connection test if enabled
- Scheduler: verify last tick within 2x interval

## Alert Thresholds
If 3 consecutive heartbeats fail → alert admin via webhook
If inference latency exceeds 30 seconds → log warning
If database query latency exceeds 5 seconds → log warning

## Monitoring
Write heartbeat timestamp to health_check_logs table
Track: inference_ok, database_ok, smtp_ok, latency_ms

## Platform Ops Skill — Autonomous Health Monitoring

The `skills/refinet-platform-ops/` skill extends the heartbeat protocol with:

- **Comprehensive health checker** (`scripts/health_check.py`): Tests API, BitNet, DB, SMTP, disk, and memory. Emails admin via self-hosted SMTP when issues are found.
- **Zero-cost agent pipeline** (`scripts/run_agent.sh`): 4-tier LLM fallback (Claude Code CLI → Ollama → BitNet → Gemini Flash) with 7-layer context injection.
- **Admin email alerts**: 8 categories (HEALTH, SECURITY, AGENT, DEPLOY, CHAIN, REGISTRY, KNOWLEDGE, MAINTENANCE) via self-hosted SMTP on port 8025.
- **Cron-driven pipeline**: heartbeat (60s), inference check (5m), security audit (15m), memory cleanup (1h), daily summary, weekly audit.
- **File-based memory**: Agent state persisted to `memory/{working,episodic,semantic,procedural}/` for cross-run continuity.

Run manually:
```bash
python3 skills/refinet-platform-ops/scripts/health_check.py --email --always
./skills/refinet-platform-ops/scripts/run_agent.sh platform-ops "Run health check"
```

### Knowledge Curator Integration

The heartbeat system also routes knowledge-related events to the curator agent:

| Interval | Agent | Task |
|---|---|---|
| 30m | knowledge-curator | Check for pending document uploads |
| 6h | knowledge-curator | Orphan detection + stale chunk pruning |
| 6h | knowledge-curator | CAG index sync with registry |
| Daily 05:30 | knowledge-curator | Embedding quality benchmark |
| Daily 06:00 | knowledge-curator | Knowledge base digest email |

Run manually:
```bash
python3 skills/refinet-knowledge-curator/scripts/knowledge_health.py --repair --email
./skills/refinet-platform-ops/scripts/run_agent.sh knowledge-curator "Check CAG sync status"
```

### Contract Watcher Integration

| Interval | Agent | Task |
|---|---|---|
| 5m | contract-watcher | Process new chain events |
| 15m | contract-watcher | Scan new ABI uploads for dangerous patterns |
| 4h | contract-watcher | Watched contract activity check |
| 12h | contract-watcher | Cross-chain bridge correlation |
| Weekly Mon 06:30 | contract-watcher | Chain intelligence report |

Run manually:
```bash
python3 skills/refinet-contract-watcher/scripts/contract_scan.py --scan-abis --email
./skills/refinet-platform-ops/scripts/run_agent.sh contract-watcher "Check bridge activity"
```

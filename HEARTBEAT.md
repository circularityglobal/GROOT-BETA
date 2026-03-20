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

### Repo Migrator Integration

The repo migrator is primarily user-triggered (not heartbeat-driven), but has maintenance tasks:

| Interval | Agent | Task |
|---|---|---|
| User request | repo-migrator | Full GitHub-to-REFINET migration pipeline |
| Daily 07:00 | repo-migrator | Retry failed migrations |
| Weekly Mon 07:00 | repo-migrator | Migration stats digest |

When a migration completes, the repo-migrator delegates to:
- `knowledge-curator` → CAG index sync for new contracts
- `contract-watcher` → ABI security analysis for dangerous patterns

Run manually:
```bash
python3 skills/refinet-repo-migrator/scripts/repo_migrate.py https://github.com/owner/repo --dry-run
./skills/refinet-platform-ops/scripts/run_agent.sh repo-migrator "Retry failed migrations"
```

### Security Sentinel Integration

The security sentinel runs continuous defense monitoring:

| Interval | Agent | Task |
|---|---|---|
| 15m | security-sentinel | Auth anomaly detection (SIWE, TOTP, JWT, credential stuffing) |
| 1h | security-sentinel | Rate limit pattern analysis (normal vs abuse classification) |
| Daily 05:00 | security-sentinel | 24-hour security briefing email |
| Weekly Sun 04:00 | security-sentinel | TLS certificate expiry check |
| Weekly Sun 04:30 | security-sentinel | BYOK Security Gate validation |
| Weekly Sun 05:00 | security-sentinel | SIWE wallet forensics (7-day window) |

The sentinel observes and reports — it never blocks, bans, or modifies. All enforcement requires explicit admin approval.

Run manually:
```bash
python3 skills/refinet-security-sentinel/scripts/security_scan.py --full --email
./skills/refinet-platform-ops/scripts/run_agent.sh security-sentinel "Run full security audit"
```

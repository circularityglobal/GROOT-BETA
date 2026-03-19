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

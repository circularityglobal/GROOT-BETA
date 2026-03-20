# Platform Ops Setup Guide

## What It Does

The platform-ops agent provides autonomous infrastructure monitoring:
- Checks 6 subsystems in parallel (API, BitNet inference, database, SMTP, disk, memory)
- Sends HTML email alerts when subsystem failures or threshold breaches are detected
- Compiles daily 24h platform health summaries with uptime, latency, and error rates
- Runs weekly full audits covering DB integrity, chain listeners, registry stats
- Delegates memory cleanup and log rotation to the maintenance agent

## Prerequisites

1. `.env` configured with `ADMIN_EMAIL`, `SMTP_HOST`, `SMTP_PORT`
2. BitNet inference server running (or health check reports it as down)
3. Both `data/public.db` and `data/internal.db` initialized

## Testing Locally

```bash
# Quick health check (stdout only)
python3 skills/refinet-platform-ops/scripts/health_check.py

# Health check + email report (only on failure)
python3 skills/refinet-platform-ops/scripts/health_check.py --email

# Health check + email report (always, even if healthy)
python3 skills/refinet-platform-ops/scripts/health_check.py --email --always

# Run agent task through LLM fallback chain
./skills/refinet-platform-ops/scripts/run_agent.sh platform-ops "Run health check and email admin"
```

## Cron Installation

```bash
# Install cron entries
sudo bash scripts/install_platform_ops_cron.sh

# Remove cron entries
sudo bash scripts/install_platform_ops_cron.sh --remove
```

GitHub Actions: `.github/workflows/platform-ops.yml` (daily + weekly schedules)

## Cost Breakdown

| Component | Monthly Cost |
|---|---|
| Health check scripts | $0 (local Python) |
| LLM fallback chain | $0 (Claude Code / Ollama / BitNet / Gemini free) |
| Self-hosted SMTP | $0 (Haraka) |
| GitHub Actions | $0 (shared with other agents) |
| **Total** | **$0/month** |

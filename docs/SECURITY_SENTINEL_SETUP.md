# Security Sentinel Setup Guide

## What It Does

The security-sentinel agent provides autonomous defense monitoring:
- Runs 6 anomaly detection rules against the audit log every 15 minutes
- Detects SIWE brute force, TOTP brute force, credential stuffing, expired JWT reuse, API key abuse
- Classifies rate limit patterns as NORMAL, TRAFFIC_SPIKE, or LIKELY_ABUSE hourly
- Checks TLS certificate expiry weekly (alerts at 30, 14, 7 days)
- Validates BYOK Security Gate enforcement (3-layer auth for key management)
- Analyzes wallet behavior for endpoint sweeping, multi-IP usage, high error rates

The sentinel observes and reports — it never blocks, bans, or modifies. All enforcement requires explicit admin approval.

## Prerequisites

1. `refinet-platform-ops` skill installed (provides `run_agent.sh` fallback chain)
2. Audit log table populated (append-only `admin_audit_log` in internal.db)
3. `.env` configured with `ADMIN_EMAIL`, `SMTP_HOST`, `SMTP_PORT`
4. TLS configured with Let's Encrypt for certificate monitoring

## Testing Locally

```bash
# TLS certificate check only
python3 skills/refinet-security-sentinel/scripts/security_scan.py --tls

# BYOK gate validation only
python3 skills/refinet-security-sentinel/scripts/security_scan.py --gate

# Full security scan + email
python3 skills/refinet-security-sentinel/scripts/security_scan.py --full --email

# Run sentinel agent task through LLM fallback chain
./skills/refinet-platform-ops/scripts/run_agent.sh security-sentinel "Run full security audit"
```

## Cron Installation

```bash
# Install cron entries
sudo bash scripts/install_security_sentinel_cron.sh

# Remove cron entries
sudo bash scripts/install_security_sentinel_cron.sh --remove
```

GitHub Actions: `.github/workflows/security-sentinel.yml` (daily + weekly schedules)

## Cost Breakdown

| Component | Monthly Cost |
|---|---|
| Audit log analysis | $0 (SQLite queries, local CPU) |
| TLS certificate checks | $0 (openssl s_client) |
| LLM fallback chain | $0 (Claude Code / Ollama / BitNet / Gemini free) |
| Self-hosted SMTP | $0 (Haraka) |
| GitHub Actions | $0 (shared with other agents) |
| **Total** | **$0/month** |

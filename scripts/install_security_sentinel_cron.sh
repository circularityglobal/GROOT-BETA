#!/bin/bash
# =============================================================================
# REFINET Security Sentinel — Cron Installation
# =============================================================================
# Installs cron entries for autonomous defense monitoring.
# The sentinel observes and reports — it never blocks, bans, or modifies.
# Reuses run_agent.sh from platform-ops for LLM fallback chain.
#
# Usage:
#   sudo bash scripts/install_security_sentinel_cron.sh
#   sudo bash scripts/install_security_sentinel_cron.sh --remove
# =============================================================================

set -euo pipefail

REPO_ROOT="${REFINET_ROOT:-.}"
AGENT_SCRIPT="${REPO_ROOT}/skills/refinet-platform-ops/scripts/run_agent.sh"
SCAN_SCRIPT="${REPO_ROOT}/skills/refinet-security-sentinel/scripts/security_scan.py"
chmod +x "$AGENT_SCRIPT" 2>/dev/null || true

if [ "${1:-}" = "--remove" ]; then
    echo "[security-sentinel] Removing cron entries..."
    crontab -l 2>/dev/null | grep -v "REFINET-SEC" | crontab - 2>/dev/null || true
    echo "[security-sentinel] Removed."
    exit 0
fi

echo "[security-sentinel] Installing cron entries..."

crontab -l 2>/dev/null | grep -v "REFINET-SEC" | crontab - 2>/dev/null || true
(crontab -l 2>/dev/null; cat <<CRON

# ── REFINET-SEC: Security Sentinel Agent ────────────────────────
# Every 15 minutes — authentication anomaly scan
*/15 * * * * cd ${REPO_ROOT} && python3 ${SCAN_SCRIPT} --auth --email >> /var/log/refinet-sec.log 2>&1 # REFINET-SEC

# Every hour — rate limit pattern analysis
0 * * * * cd ${REPO_ROOT} && python3 ${SCAN_SCRIPT} --rates >> /var/log/refinet-sec.log 2>&1 # REFINET-SEC

# Daily 05:00 UTC — security briefing email
0 5 * * * cd ${REPO_ROOT} && python3 ${SCAN_SCRIPT} --full --email >> /var/log/refinet-sec.log 2>&1 # REFINET-SEC

# Weekly Sunday 04:00 UTC — TLS certificate check
0 4 * * 0 cd ${REPO_ROOT} && python3 ${SCAN_SCRIPT} --tls --email >> /var/log/refinet-sec.log 2>&1 # REFINET-SEC

# Weekly Sunday 04:30 UTC — BYOK Security Gate validation
30 4 * * 0 cd ${REPO_ROOT} && python3 ${SCAN_SCRIPT} --gate --email >> /var/log/refinet-sec.log 2>&1 # REFINET-SEC

# Weekly Sunday 05:00 UTC — wallet forensics
0 5 * * 0 cd ${REPO_ROOT} && ${AGENT_SCRIPT} security-sentinel "Analyze SIWE-authenticated wallets from past 7 days, flag endpoint sweeping and multi-IP usage" >> /var/log/refinet-sec.log 2>&1 # REFINET-SEC
CRON
) | crontab -

echo "[security-sentinel] Cron installed. Logs: /var/log/refinet-sec.log"
crontab -l | grep "REFINET-SEC"

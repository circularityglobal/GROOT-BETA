#!/bin/bash
# =============================================================================
# REFINET Platform Ops — Cron Installation
# =============================================================================
# Installs cron entries for autonomous infrastructure monitoring.
# Reuses run_agent.sh for LLM fallback chain.
#
# Usage:
#   sudo bash scripts/install_platform_ops_cron.sh
#   sudo bash scripts/install_platform_ops_cron.sh --remove
# =============================================================================

set -euo pipefail

REPO_ROOT="${REFINET_ROOT:-.}"
AGENT_SCRIPT="${REPO_ROOT}/skills/refinet-platform-ops/scripts/run_agent.sh"
HEALTH_SCRIPT="${REPO_ROOT}/skills/refinet-platform-ops/scripts/health_check.py"
chmod +x "$AGENT_SCRIPT" 2>/dev/null || true

if [ "${1:-}" = "--remove" ]; then
    echo "[platform-ops] Removing cron entries..."
    crontab -l 2>/dev/null | grep -v "REFINET-OPS" | crontab - 2>/dev/null || true
    echo "[platform-ops] Removed."
    exit 0
fi

echo "[platform-ops] Installing cron entries..."

crontab -l 2>/dev/null | grep -v "REFINET-OPS" | crontab - 2>/dev/null || true
(crontab -l 2>/dev/null; cat <<CRON

# ── REFINET-OPS: Platform Ops Agent ─────────────────────────────
# Every 5 minutes — inference health check
*/5 * * * * cd ${REPO_ROOT} && python3 ${HEALTH_SCRIPT} >> /var/log/refinet-ops.log 2>&1 # REFINET-OPS

# Every hour — memory and disk cleanup
0 * * * * cd ${REPO_ROOT} && ${AGENT_SCRIPT} platform-ops "Check working memory for stale state, prune episodic logs older than 30 days, check disk usage" >> /var/log/refinet-ops.log 2>&1 # REFINET-OPS

# Daily 06:00 UTC — platform health summary + email
0 6 * * * cd ${REPO_ROOT} && python3 ${HEALTH_SCRIPT} --email --always >> /var/log/refinet-ops.log 2>&1 # REFINET-OPS

# Weekly Monday 06:00 UTC — full platform audit
0 6 * * 1 cd ${REPO_ROOT} && ${AGENT_SCRIPT} platform-ops "Full platform audit: all subsystems, agent performance, DB integrity, SMTP, chain listeners, registry stats" >> /var/log/refinet-ops.log 2>&1 # REFINET-OPS
CRON
) | crontab -

echo "[platform-ops] Cron installed. Logs: /var/log/refinet-ops.log"
crontab -l | grep "REFINET-OPS"

#!/bin/bash
# =============================================================================
# REFINET Contract Watcher — Cron Installation
# =============================================================================
# Installs cron entries for autonomous on-chain intelligence.
# Reuses run_agent.sh from the platform-ops skill for LLM fallback.
#
# Usage:
#   sudo bash scripts/install_contract_watcher_cron.sh
#   sudo bash scripts/install_contract_watcher_cron.sh --remove
# =============================================================================

set -euo pipefail

REPO_ROOT="${REFINET_ROOT:-.}"
AGENT_SCRIPT="${REPO_ROOT}/skills/refinet-platform-ops/scripts/run_agent.sh"
SCAN_SCRIPT="${REPO_ROOT}/skills/refinet-contract-watcher/scripts/contract_scan.py"
chmod +x "$AGENT_SCRIPT" 2>/dev/null || true

if [ "${1:-}" = "--remove" ]; then
    echo "[contract-watcher] Removing cron entries..."
    crontab -l 2>/dev/null | grep -v "REFINET-CHAIN" | crontab - 2>/dev/null || true
    echo "[contract-watcher] Removed."
    exit 0
fi

echo "[contract-watcher] Installing cron entries..."

crontab -l 2>/dev/null | grep -v "REFINET-CHAIN" | crontab - 2>/dev/null || true
(crontab -l 2>/dev/null; cat <<CRON

# ── REFINET-CHAIN: Contract Watcher Agent ───────────────────────
# Every 15 minutes — scan new ABIs for dangerous patterns
*/15 * * * * cd ${REPO_ROOT} && python3 ${SCAN_SCRIPT} --scan-abis >> /var/log/refinet-chain.log 2>&1 # REFINET-CHAIN

# Every 4 hours — watched contract activity check
0 */4 * * * cd ${REPO_ROOT} && ${AGENT_SCRIPT} contract-watcher "Check watched contract activity and alert on anomalies" >> /var/log/refinet-chain.log 2>&1 # REFINET-CHAIN

# Every 12 hours — bridge correlation
0 */12 * * * cd ${REPO_ROOT} && ${AGENT_SCRIPT} contract-watcher "Correlate cross-chain bridge events" >> /var/log/refinet-chain.log 2>&1 # REFINET-CHAIN

# Weekly Monday 06:30 — chain intelligence report
30 6 * * 1 cd ${REPO_ROOT} && ${AGENT_SCRIPT} contract-watcher "Weekly chain intelligence report" >> /var/log/refinet-chain.log 2>&1 # REFINET-CHAIN
CRON
) | crontab -

echo "[contract-watcher] Cron installed. Logs: /var/log/refinet-chain.log"
crontab -l | grep "REFINET-CHAIN"

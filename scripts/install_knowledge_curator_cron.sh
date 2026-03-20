#!/bin/bash
# =============================================================================
# REFINET Knowledge Curator — Cron Installation
# =============================================================================
# Installs cron entries for autonomous RAG/CAG maintenance.
# Reuses run_agent.sh from the platform-ops skill for LLM fallback.
#
# Usage:
#   sudo bash scripts/install_knowledge_curator_cron.sh
#   sudo bash scripts/install_knowledge_curator_cron.sh --remove
# =============================================================================

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/refinet/app}"
AGENT_SCRIPT="${REPO_ROOT}/skills/refinet-platform-ops/scripts/run_agent.sh"
HEALTH_SCRIPT="${REPO_ROOT}/skills/refinet-knowledge-curator/scripts/knowledge_health.py"
VENV="${VENV:-/opt/refinet/venv}"
MARKER="REFINET-KNOWLEDGE"

if [ "${1:-}" = "--remove" ]; then
    echo "[knowledge-curator] Removing cron entries..."
    crontab -l 2>/dev/null | grep -v "$MARKER" | crontab -
    echo "[knowledge-curator] Removed."
    exit 0
fi

echo "[knowledge-curator] Installing cron entries..."

# Build new cron entries
CRON_ENTRIES=$(cat <<CRON
# ── REFINET-KNOWLEDGE: Autonomous Knowledge Curator ─────────────
# Every 6 hours — orphan repair + CAG sync
0 */6 * * * cd ${REPO_ROOT} && ${VENV}/bin/python3 ${HEALTH_SCRIPT} --repair --email >> /var/log/refinet-knowledge.log 2>&1 # ${MARKER}

# Daily quality benchmark at 05:30 UTC
30 5 * * * cd ${REPO_ROOT} && ${AGENT_SCRIPT} knowledge-curator "Run embedding benchmark and check for quality drift" >> /var/log/refinet-knowledge.log 2>&1 # ${MARKER}

# Daily knowledge digest at 06:00 UTC
0 6 * * * cd ${REPO_ROOT} && ${AGENT_SCRIPT} knowledge-curator "Compile 24h knowledge digest and email admin" >> /var/log/refinet-knowledge.log 2>&1 # ${MARKER}
CRON
)

# Remove existing entries, append new ones
(crontab -l 2>/dev/null | grep -v "$MARKER"; echo "$CRON_ENTRIES") | crontab -

echo "[knowledge-curator] Cron entries installed:"
crontab -l | grep "$MARKER"
echo "[knowledge-curator] Done."

#!/bin/bash
# =============================================================================
# REFINET Repo Migrator — Cron Installation
# =============================================================================
# Installs cron entries for automated migration retries and stats.
# Migrations are primarily user-triggered; cron handles maintenance only.
# Reuses run_agent.sh from platform-ops for LLM fallback chain.
#
# Usage:
#   sudo bash scripts/install_repo_migrator_cron.sh
#   sudo bash scripts/install_repo_migrator_cron.sh --remove
# =============================================================================

set -euo pipefail

REPO_ROOT="${REFINET_ROOT:-.}"
AGENT_SCRIPT="${REPO_ROOT}/skills/refinet-platform-ops/scripts/run_agent.sh"
MIGRATE_SCRIPT="${REPO_ROOT}/skills/refinet-repo-migrator/scripts/repo_migrate.py"
chmod +x "$AGENT_SCRIPT" 2>/dev/null || true

if [ "${1:-}" = "--remove" ]; then
    echo "[repo-migrator] Removing cron entries..."
    crontab -l 2>/dev/null | grep -v "REFINET-MIGRATE" | crontab - 2>/dev/null || true
    echo "[repo-migrator] Removed."
    exit 0
fi

echo "[repo-migrator] Installing cron entries..."

crontab -l 2>/dev/null | grep -v "REFINET-MIGRATE" | crontab - 2>/dev/null || true
(crontab -l 2>/dev/null; cat <<CRON

# ── REFINET-MIGRATE: Repo Migrator Agent ────────────────────────
# Daily 07:00 UTC — retry failed migrations
0 7 * * * cd ${REPO_ROOT} && python3 ${MIGRATE_SCRIPT} --retry --email >> /var/log/refinet-migrate.log 2>&1 # REFINET-MIGRATE

# Weekly Monday 07:00 UTC — migration stats digest
0 7 * * 1 cd ${REPO_ROOT} && python3 ${MIGRATE_SCRIPT} --stats --email >> /var/log/refinet-migrate.log 2>&1 # REFINET-MIGRATE
CRON
) | crontab -

echo "[repo-migrator] Cron installed. Logs: /var/log/refinet-migrate.log"
crontab -l | grep "REFINET-MIGRATE"

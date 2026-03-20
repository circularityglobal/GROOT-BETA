#!/bin/bash
# =============================================================================
# REFINET Cloud — Database Backup Script
# =============================================================================
# Safe online backup of both SQLite databases using .backup command (WAL-safe).
# Compresses with gzip (~70% reduction). Retains last 7 daily backups.
#
# Usage:
#   bash scripts/backup_databases.sh
#   bash scripts/backup_databases.sh --dry-run
#
# Add to platform-ops cron (03:00 UTC daily):
#   0 3 * * * cd /path/to/groot && bash scripts/backup_databases.sh
# =============================================================================

set -euo pipefail

REPO_ROOT="${REFINET_ROOT:-.}"
DATA_DIR="${REPO_ROOT}/data"
BACKUP_BASE="${DATA_DIR}/backups"
DATE=$(date -u +"%Y-%m-%d")
BACKUP_DIR="${BACKUP_BASE}/${DATE}"
DRY_RUN="${1:-}"
RETENTION_DAYS=7

PUBLIC_DB="${DATA_DIR}/public.db"
INTERNAL_DB="${DATA_DIR}/internal.db"

log() { echo "[backup $(date -u +%H:%M:%S)] $1"; }

if [ "$DRY_RUN" = "--dry-run" ]; then
    log "DRY RUN — would back up to ${BACKUP_DIR}/"
    [ -f "$PUBLIC_DB" ] && log "  public.db: $(du -h "$PUBLIC_DB" | cut -f1)" || log "  public.db: NOT FOUND"
    [ -f "$INTERNAL_DB" ] && log "  internal.db: $(du -h "$INTERNAL_DB" | cut -f1)" || log "  internal.db: NOT FOUND"
    exit 0
fi

mkdir -p "$BACKUP_DIR"

# Backup public.db
if [ -f "$PUBLIC_DB" ]; then
    log "Backing up public.db..."
    sqlite3 "$PUBLIC_DB" ".backup '${BACKUP_DIR}/public.db'"
    gzip -f "${BACKUP_DIR}/public.db"
    log "  → ${BACKUP_DIR}/public.db.gz ($(du -h "${BACKUP_DIR}/public.db.gz" | cut -f1))"
else
    log "WARNING: public.db not found at ${PUBLIC_DB}"
fi

# Backup internal.db
if [ -f "$INTERNAL_DB" ]; then
    log "Backing up internal.db..."
    sqlite3 "$INTERNAL_DB" ".backup '${BACKUP_DIR}/internal.db'"
    gzip -f "${BACKUP_DIR}/internal.db"
    log "  → ${BACKUP_DIR}/internal.db.gz ($(du -h "${BACKUP_DIR}/internal.db.gz" | cut -f1))"
else
    log "WARNING: internal.db not found at ${INTERNAL_DB}"
fi

# Prune backups older than retention period
log "Pruning backups older than ${RETENTION_DAYS} days..."
if [ -d "$BACKUP_BASE" ]; then
    find "$BACKUP_BASE" -mindepth 1 -maxdepth 1 -type d -mtime +${RETENTION_DAYS} -exec rm -rf {} \; 2>/dev/null || true
    REMAINING=$(find "$BACKUP_BASE" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')
    log "  ${REMAINING} backup(s) retained"
fi

log "Backup complete."

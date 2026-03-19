# Scripts — Administration & Operations

All scripts run from the project root. Most require an active virtualenv with dependencies installed.

```bash
source venv/bin/activate  # Required for Python scripts
```

---

## Admin & Deployment

| Script | Purpose | Usage |
|---|---|---|
| `admin.py` | CLI for user management, roles, secrets, audit logs | `python3 scripts/admin.py --help` |
| `bootstrap.sh` | Full server setup (packages, firewall, venv, BitNet, systemd, DB init) | `bash scripts/bootstrap.sh` |
| `deploy.sh` | Redeploy after code changes (git pull, deps, restart services) | `bash scripts/deploy.sh` |
| `deploy-product.sh` | Deploy product subdomains (Pillars, Browser) | `bash scripts/deploy-product.sh pillars` |
| `generate_env.sh` | Generate a new .env file with random secrets | `bash scripts/generate_env.sh` |
| `rotate_secrets.sh` | Rotate encryption keys and signing secrets | `bash scripts/rotate_secrets.sh` |
| `verify_deployment.sh` | Run 20+ automated deployment verification checks | `bash scripts/verify_deployment.sh` |
| `dev.sh` | Start development servers (API + frontend) | `bash dev.sh` |

## Analysis

| Script | Purpose | Usage |
|---|---|---|
| `analysis/knowledge_coverage.py` | Report on knowledge base coverage by category | `python3 scripts/analysis/knowledge_coverage.py` |
| `analysis/platform_stats.py` | Platform-wide statistics (users, agents, contracts, etc.) | `python3 scripts/analysis/platform_stats.py` |
| `analysis/registry_report.py` | Smart contract registry analysis | `python3 scripts/analysis/registry_report.py` |
| `analysis/usage_report.py` | Usage analytics and billing summary | `python3 scripts/analysis/usage_report.py` |

## Chain

| Script | Purpose | Usage |
|---|---|---|
| `chain/fetch_abi.py` | Fetch contract ABI from block explorer | `python3 scripts/chain/fetch_abi.py 0xAddress --chain base` |
| `chain/monitor_address.py` | Monitor blockchain address for activity | `python3 scripts/chain/monitor_address.py 0xAddress` |
| `chain/read_contract.py` | Read contract state via RPC | `python3 scripts/chain/read_contract.py 0xAddress balanceOf` |

## DApp

| Script | Purpose | Usage |
|---|---|---|
| `dapp/build_dapp.py` | Build a DApp from registry contract + template | `python3 scripts/dapp/build_dapp.py --template token-dashboard` |
| `dapp/list_templates.py` | List available DApp templates | `python3 scripts/dapp/list_templates.py` |

## Maintenance

| Script | Purpose | Usage |
|---|---|---|
| `maintenance/backup_db.py` | Backup public.db and internal.db | `python3 scripts/maintenance/backup_db.py` |
| `maintenance/cleanup_orphans.py` | Remove orphaned records (chunks without docs, etc.) | `python3 scripts/maintenance/cleanup_orphans.py` |
| `maintenance/prune_telemetry.py` | Remove telemetry records older than 30 days | `python3 scripts/maintenance/prune_telemetry.py` |
| `maintenance/rebuild_fts_index.py` | Rebuild FTS5 full-text search index | `python3 scripts/maintenance/rebuild_fts_index.py` |
| `maintenance/reset_api_counters.py` | Reset daily API key request counters | `python3 scripts/maintenance/reset_api_counters.py` |
| `maintenance/rotate_secrets.py` | Rotate server secrets and re-encrypt | `python3 scripts/maintenance/rotate_secrets.py` |
| `maintenance/backfill_embeddings.py` | Backfill missing semantic embeddings | `python3 scripts/maintenance/backfill_embeddings.py` |
| `maintenance/backfill_sdk_knowledge.py` | Sync SDK definitions into knowledge base | `python3 scripts/maintenance/backfill_sdk_knowledge.py` |

## Ops

| Script | Purpose | Usage |
|---|---|---|
| `ops/db_stats.py` | Database table sizes and record counts | `python3 scripts/ops/db_stats.py` |
| `ops/health_report.py` | System health report (BitNet, DB, SMTP, scheduler) | `python3 scripts/ops/health_report.py` |

## Seed (Development)

| Script | Purpose | Usage |
|---|---|---|
| `seed/seed_contracts.py` | Seed sample smart contracts into registry | `python3 scripts/seed/seed_contracts.py` |
| `seed/seed_knowledge.py` | Seed knowledge base with platform documentation | `python3 scripts/seed/seed_knowledge.py` |
| `seed/ingest_docs.py` | Ingest documents from a directory into knowledge base | `python3 scripts/seed/ingest_docs.py /path/to/docs` |

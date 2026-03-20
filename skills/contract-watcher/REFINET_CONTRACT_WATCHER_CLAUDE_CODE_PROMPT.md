# REFINET Contract Watcher — Claude Code Installation Prompt

> **Copy everything below the line into Claude Code as a single prompt.**
> Run from inside your cloned `GROOT-BETA/` repo directory.
> Drop the 5 skill files from the `refinet-contract-watcher/` folder into the conversation so Claude Code can read them.

---

## The Prompt

```
You are operating inside the GROOT-BETA repository (https://github.com/circularityglobal/GROOT-BETA), which is the REFINET Cloud sovereign AI platform. Your job is to install the `refinet-contract-watcher` skill — the third autonomous agent skill in the platform's zero-cost agent pipeline (after platform-ops and knowledge-curator). Follow every step precisely. Do not skip steps. Do not ask for confirmation — execute sequentially.

## CONTEXT

REFINET Cloud has a chain listener system (/chain/*) that monitors EVM-compatible chains (Ethereum, Polygon, Arbitrum, Optimism, Base, Sepolia) for events. It also has a smart contract registry (/registry/*) where users upload ABIs. Currently these systems capture raw data but lack an intelligence layer. The contract-watcher agent adds:
- Real-time event interpretation using ABI context
- Automatic security analysis of uploaded ABIs (delegatecall, selfdestruct, tx.origin, etc.)
- Activity monitoring for starred/forked contracts
- Cross-chain bridge transaction correlation
- Weekly chain intelligence reports

The platform-ops and knowledge-curator skills are already installed. This skill follows the same pattern: SKILL.md + scripts/ + references/, reuses run_agent.sh for the LLM fallback chain, same email alerting.

Tech stack: FastAPI, SQLite WAL, public RPCs (no API keys), sentence-transformers for CAG embeddings, self-hosted SMTP on port 8025, AGPL-3.0, zero recurring cost.

## STEP 1 — Install the skill files

Create the following from the provided skill package:

### 1a. Create `skills/refinet-contract-watcher/SKILL.md`

Main skill file covering:
- Part 1: On-chain architecture (chain listener flow, 6 supported chains, storage schema, dangerous operation patterns with 10 categories)
- Part 2: Autonomous pipelines (event interpretation with 4-tier classification, ABI security analysis with regex pattern scanning, contract activity monitoring with anomaly detection, cross-chain bridge correlation with known bridge contracts)
- Part 3: Admin email notifications (5 alert categories, security analysis template, weekly report template)
- Part 4: Cron schedule (5 scheduled tasks from 5-minute event processing to weekly reports)
- Part 5: Operating procedures (contract scanning, event querying, monitoring setup, bridge analysis)
- Part 6: Safety constraints
- Part 7: Reference file pointers

Read the provided SKILL.md and copy it exactly.

### 1b. Create `skills/refinet-contract-watcher/scripts/contract_scan.py`

The on-chain intelligence scanner. It:
- Finds ABI uploads that haven't been security-analyzed
- Scans ABIs for 8 dangerous patterns (delegatecall, selfdestruct, tx.origin, unchecked call, infinite approval, inline assembly, proxy patterns, ownership transfer)
- Stores security flags in the database
- Reports chain event statistics (listeners, events, unprocessed count)
- Reports registry statistics (projects, ABIs, flagged, starred)
- Emails admin with formatted HTML report
- Returns exit code 1 if any CRITICAL flags found

### 1c. Create `skills/refinet-contract-watcher/references/chain-api.md`

Chain listener API reference: all endpoints, create listener schema, captured event schema, event status lifecycle, chain RPC configuration for all 6 chains (with free public RPC URLs), and database schemas for chain_listeners, chain_events, and contract_security_flags.

### 1d. Create `skills/refinet-contract-watcher/references/registry-api.md`

Smart contract registry API reference: all endpoints, ABI upload/detail schemas, 10 project categories, security flag format, and SDK generation pipeline.

## STEP 2 — Create the cron configuration

Create `configs/contract-watcher-cron.yaml`:

```yaml
# REFINET Contract Watcher — Autonomous On-Chain Intelligence Schedule
# All tasks execute through the zero-cost LLM fallback chain
# All RPC calls use free public endpoints — no API keys
# Total recurring cost: $0

schedules:
  # Every 5 minutes — process new captured events
  - name: event-processing
    interval: 5m
    agent: contract-watcher
    task: >
      Check chain_events table for unprocessed events (status = 'raw').
      For each event, load the contract ABI from the registry, decode
      event parameters, classify as routine/notable/anomalous/dangerous.
      Update event status. Alert admin for anomalous or dangerous events.

  # Every 15 minutes — scan new ABI uploads
  - name: abi-security-scan
    interval: 15m
    agent: contract-watcher
    task: >
      Check contract_abis table for ABIs not yet security-analyzed.
      For each, run dangerous pattern analysis (delegatecall, selfdestruct,
      tx.origin, unchecked call, infinite approval, assembly, proxy, ownership).
      Store flags in contract_security_flags. Email admin for HIGH or CRITICAL.

  # Every 4 hours — watched contract activity check
  - name: activity-monitor
    interval: 4h
    agent: contract-watcher
    task: >
      Get all starred/forked contracts. For each, check on-chain activity
      via public RPC. Compare against historical baselines in episodic memory.
      Alert admin on anomalies: tx spike above 3x, balance drop above 50%,
      balance surge above 5x baseline.

  # Every 12 hours — cross-chain bridge correlation
  - name: bridge-correlation
    interval: 12h
    agent: contract-watcher
    task: >
      Scan chain_events for transactions involving known bridge contracts
      (Optimism, Arbitrum, Base, Polygon bridges). Correlate L1 deposits
      with L2 arrivals. Flag unmatched deposits. Report bridge summary.

  # Weekly Monday at 06:30 UTC — chain intelligence report
  - name: weekly-report
    cron: "30 6 * * 1"
    agent: contract-watcher
    task: >
      Compile weekly chain intelligence: contracts monitored, events per chain,
      security flags by severity, anomalous events, bridge transactions,
      new ABIs analyzed, chains active vs inactive. HTML email to admin.
```

## STEP 3 — Create GitHub Actions workflow

Create `.github/workflows/contract-watcher.yml`:

```yaml
name: REFINET Contract Watcher — Autonomous On-Chain Intelligence

on:
  schedule:
    # Daily ABI scan at 07:00 UTC
    - cron: '0 7 * * *'
    # Weekly chain intelligence report Monday 06:30 UTC
    - cron: '30 6 * * 1'
  workflow_dispatch:
    inputs:
      task:
        description: 'Contract watcher task'
        required: false
        default: 'Scan all unanalyzed ABIs and email security report'

jobs:
  abi-scan:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Scan ABIs for dangerous patterns
        run: python skills/refinet-contract-watcher/scripts/contract_scan.py --scan-abis --email
        env:
          DATABASE_PATH: ${{ secrets.DATABASE_PATH }}
          ADMIN_EMAIL: ${{ secrets.ADMIN_EMAIL }}
          SMTP_HOST: ${{ secrets.SMTP_HOST }}
          SMTP_PORT: ${{ secrets.SMTP_PORT }}
          MAIL_FROM: ${{ secrets.MAIL_FROM }}

  watcher-task:
    if: github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - run: sudo apt-get install -y jq
      - name: Run watcher agent
        run: |
          chmod +x skills/refinet-platform-ops/scripts/run_agent.sh
          ./skills/refinet-platform-ops/scripts/run_agent.sh \
            contract-watcher \
            "${{ github.event.inputs.task }}"
        env:
          REFINET_ROOT: ${{ github.workspace }}
          BITNET_HOST: ${{ secrets.BITNET_HOST }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          ADMIN_EMAIL: ${{ secrets.ADMIN_EMAIL }}
          SMTP_HOST: ${{ secrets.SMTP_HOST }}
          SMTP_PORT: ${{ secrets.SMTP_PORT }}

  weekly-report:
    if: github.event.schedule == '30 6 * * 1'
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - run: sudo apt-get install -y jq
      - name: Run weekly chain intelligence report
        run: |
          chmod +x skills/refinet-platform-ops/scripts/run_agent.sh
          ./skills/refinet-platform-ops/scripts/run_agent.sh \
            contract-watcher \
            "Compile weekly chain intelligence report with full stats and email admin"
        env:
          REFINET_ROOT: ${{ github.workspace }}
          BITNET_HOST: ${{ secrets.BITNET_HOST }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          ADMIN_EMAIL: ${{ secrets.ADMIN_EMAIL }}
          SMTP_HOST: ${{ secrets.SMTP_HOST }}
          SMTP_PORT: ${{ secrets.SMTP_PORT }}
```

## STEP 4 — Add cron entries to server installer

Create `scripts/install_contract_watcher_cron.sh` following the same pattern as `scripts/install_platform_ops_cron.sh`:

```bash
#!/bin/bash
set -euo pipefail
REPO_ROOT="${REFINET_ROOT:-.}"
AGENT_SCRIPT="${REPO_ROOT}/skills/refinet-platform-ops/scripts/run_agent.sh"
SCAN_SCRIPT="${REPO_ROOT}/skills/refinet-contract-watcher/scripts/contract_scan.py"
chmod +x "$AGENT_SCRIPT" 2>/dev/null || true
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
echo "Contract watcher cron installed. Logs: /var/log/refinet-chain.log"
crontab -l | grep "REFINET-CHAIN"
```

Mark executable: `chmod +x scripts/install_contract_watcher_cron.sh`

## STEP 5 — Update AGENTS.md

Read `AGENTS.md` and enhance the `contract-watcher` entry:

```markdown

## contract-watcher

**Role**: Autonomous on-chain intelligence — event interpretation, ABI security analysis, contract activity monitoring, and cross-chain bridge correlation.

**Trigger sources**: On-chain (event captured), webhook (new ABI upload), cron (5m events, 15m ABI scan, 4h activity, 12h bridges, weekly report).

**LLM runtime**: Zero-cost fallback chain — Claude Code CLI → Ollama → BitNet → Gemini Flash.

**Tools** (MCP gateway access):
- `chain.listeners` — Create/manage event listeners
- `chain.events` — Query and interpret captured events
- `registry.search` — Search contract registry
- `registry.get_contract_sdk` — Load ABI + SDK for context
- `knowledge.search` — Search contract documentation via RAG
- `smtp.send` — Email admin alerts

**Delegation policy**: `auto` — accepts from platform-ops and orchestrator. Can delegate to knowledge-curator for contract documentation enrichment. Max depth: 3.

**Email alert categories**: ABI_SECURITY, EVENT_ANOMALY, ACTIVITY_ALERT, BRIDGE_ALERT, WEEKLY_REPORT.

**Dangerous pattern detection**: delegatecall, selfdestruct, tx.origin, unchecked call, infinite approval, inline assembly, proxy patterns, ownership transfer.

**Key files**:
- `skills/refinet-contract-watcher/SKILL.md` — Full operational manual
- `skills/refinet-contract-watcher/scripts/contract_scan.py` — ABI scanner
- `skills/refinet-contract-watcher/references/chain-api.md` — Chain API reference
- `skills/refinet-contract-watcher/references/registry-api.md` — Registry API reference
- `configs/contract-watcher-cron.yaml` — Cron schedule
- `.github/workflows/contract-watcher.yml` — GitHub Actions runner
```

## STEP 6 — Wire into HEARTBEAT.md

Append to `HEARTBEAT.md`:

```markdown

### Contract Watcher Integration

| Interval | Agent | Task |
|---|---|---|
| 5m | contract-watcher | Process new chain events |
| 15m | contract-watcher | Scan new ABI uploads for dangerous patterns |
| 4h | contract-watcher | Watched contract activity check |
| 12h | contract-watcher | Cross-chain bridge correlation |
| Weekly Mon 06:30 | contract-watcher | Chain intelligence report |
```

## STEP 7 — Create setup documentation

Create `docs/CONTRACT_WATCHER_SETUP.md`:

```markdown
# Contract Watcher Setup Guide

## What It Does

The contract-watcher agent provides autonomous on-chain intelligence:
- Scans every new ABI upload for 8 dangerous patterns (delegatecall, selfdestruct, etc.)
- Interprets captured chain events using ABI context
- Monitors starred/forked contracts for activity anomalies across 6 EVM chains
- Correlates cross-chain bridge transactions (Optimism, Arbitrum, Base, Polygon)
- Sends weekly chain intelligence reports to admin

## Prerequisites

1. `refinet-platform-ops` skill installed (provides run_agent.sh fallback chain)
2. `refinet-knowledge-curator` skill installed (provides CAG integration)
3. Chain listener system active (/chain/* endpoints)
4. Smart contract registry active (/registry/* endpoints)

## Testing Locally

\`\`\`bash
# Scan all unanalyzed ABIs
python skills/refinet-contract-watcher/scripts/contract_scan.py --scan-abis

# Full scan + email report
python skills/refinet-contract-watcher/scripts/contract_scan.py --scan-abis --email

# Run watcher agent task
./skills/refinet-platform-ops/scripts/run_agent.sh contract-watcher "Check bridge activity"
\`\`\`

## Cost Breakdown

| Component | Monthly Cost |
|---|---|
| Public RPC endpoints (6 chains) | $0 (free public RPCs) |
| ABI pattern scanning | $0 (regex, local CPU) |
| GitHub Actions | $0 (shared with other agents) |
| Self-hosted SMTP | $0 (Haraka) |
| **Total** | **$0/month** |
```

## STEP 8 — Verify and report

After completing all steps, verify:

1. `ls skills/refinet-contract-watcher/` shows: SKILL.md, scripts/, references/
2. `ls skills/refinet-contract-watcher/scripts/` shows: contract_scan.py
3. `ls skills/refinet-contract-watcher/references/` shows: chain-api.md, registry-api.md
4. `cat configs/contract-watcher-cron.yaml` exists with 5 schedule entries
5. `cat .github/workflows/contract-watcher.yml` exists with 3 jobs
6. `cat scripts/install_contract_watcher_cron.sh` exists and is executable
7. `cat docs/CONTRACT_WATCHER_SETUP.md` exists
8. `AGENTS.md` has enhanced contract-watcher entry
9. `HEARTBEAT.md` has Contract Watcher Integration table
10. Platform-ops `run_agent.sh` is reused — not duplicated

Print file summary with line counts. Confirm this is skill 3 of 4 (platform-ops → knowledge-curator → contract-watcher → security-sentinel).
```

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

```bash
# Scan all unanalyzed ABIs
python skills/refinet-contract-watcher/scripts/contract_scan.py --scan-abis

# Full scan + email report
python skills/refinet-contract-watcher/scripts/contract_scan.py --scan-abis --email

# Run watcher agent task
./skills/refinet-platform-ops/scripts/run_agent.sh contract-watcher "Check bridge activity"
```

## Cost Breakdown

| Component | Monthly Cost |
|---|---|
| Public RPC endpoints (6 chains) | $0 (free public RPCs) |
| ABI pattern scanning | $0 (regex, local CPU) |
| GitHub Actions | $0 (shared with other agents) |
| Self-hosted SMTP | $0 (Haraka) |
| **Total** | **$0/month** |

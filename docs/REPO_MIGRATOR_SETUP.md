# Repo Migrator Setup Guide

## What It Does

Users provide a GitHub URL to GROOT, and the agent:
1. Fetches the repo and finds all smart contract files
2. Detects the ecosystem (Solidity, Anchor, Move, Clarity, TEAL, etc.)
3. Compiles Solidity locally with solc-js or uses LLM parsing for non-EVM
4. Extracts ABI and classifies functions as public vs owner-only
5. Generates separate Public SDK and Owner SDK
6. Imports into the user's private GROOT Brain contract repo
7. Triggers security analysis and CAG indexing

## Supported Ecosystems

Solidity, Vyper, Anchor (Solana), Move (Sui/Aptos), Clarity (Bitcoin/Stacks), TEAL (Algorand), XRPL Hooks, Hedera HTS, Soroban (Stellar/XLM)

## Prerequisites

1. All 4 infrastructure agents installed (platform-ops, knowledge-curator, contract-watcher, security-sentinel)
2. `solc` or `solcjs` available for Solidity compilation
3. Python 3.11+ with httpx

## Testing

```bash
# Dry run — scan without importing
python skills/refinet-repo-migrator/scripts/repo_migrate.py https://github.com/OpenZeppelin/openzeppelin-contracts --dry-run

# Full migration
python skills/refinet-repo-migrator/scripts/repo_migrate.py https://github.com/Uniswap/v3-core --email

# Filter by ecosystem
python skills/refinet-repo-migrator/scripts/repo_migrate.py https://github.com/some/repo --ecosystem solidity
```

## Cost

| Component | Monthly Cost |
|---|---|
| GitHub API (public repos) | $0 (60 req/hour) |
| solc-js (WASM on ARM) | $0 |
| LLM parsing (non-EVM) | $0 (fallback chain) |
| **Total** | **$0/month** |

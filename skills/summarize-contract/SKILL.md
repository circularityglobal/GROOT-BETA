---
name: summarize-contract
description: Generate human-readable summaries of smart contract SDKs
version: "1.0"
trigger: manual
agent: contract-analyst
input: { contract_id: string, chain: string }
output: { summary: string, functions: list, risk_level: string }
---

# Summarize Contract

Parse a contract's SDK definition and produce a clear summary
of its capabilities, access patterns, and risk profile.

## Steps
1. Retrieve contract SDK from registry
2. Classify functions by category (read, write, admin, dangerous)
3. Identify access control patterns (onlyOwner, roles, public)
4. Assess risk level based on dangerous operations
5. Generate structured summary with function list

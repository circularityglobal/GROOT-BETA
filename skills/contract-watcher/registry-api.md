# REFINET Smart Contract Registry API Reference

## Registry Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/registry/projects` | JWT | Create a new project |
| `GET` | `/registry/projects` | JWT | List user's projects |
| `GET` | `/registry/projects/{id}` | JWT | Get project details |
| `PUT` | `/registry/projects/{id}` | JWT | Update project metadata |
| `DELETE` | `/registry/projects/{id}` | JWT | Delete project |
| `POST` | `/registry/projects/{id}/abis` | JWT | Upload ABI to project |
| `GET` | `/registry/projects/{id}/abis` | JWT | List project ABIs |
| `GET` | `/registry/projects/{id}/abis/{abi_id}` | JWT | Get ABI details |
| `POST` | `/registry/projects/{id}/star` | JWT | Star a project |
| `DELETE` | `/registry/projects/{id}/star` | JWT | Unstar a project |
| `POST` | `/registry/projects/{id}/fork` | JWT | Fork a project |
| `GET` | `/explore` | None | Public explorer — browse all public projects |
| `GET` | `/explore/categories` | None | List categories |
| `GET` | `/explore/search` | None | Search projects by name/category/chain |

## ABI Upload Request

```json
{
  "chain_id": 1,
  "contract_address": "0x1234...abcd",
  "abi": [...],
  "name": "MyToken",
  "category": "Token",
  "compiler_version": "0.8.20"
}
```

## ABI Detail Response

```json
{
  "id": "abi_abc123",
  "project_id": "proj_def456",
  "chain_id": 1,
  "contract_address": "0x1234...abcd",
  "name": "MyToken",
  "category": "Token",
  "functions": [
    {
      "name": "transfer",
      "signature": "transfer(address,uint256)",
      "selector": "0xa9059cbb",
      "inputs": [
        {"name": "to", "type": "address"},
        {"name": "amount", "type": "uint256"}
      ],
      "outputs": [{"name": "", "type": "bool"}],
      "state_mutability": "nonpayable",
      "is_dangerous": false
    }
  ],
  "events": [
    {
      "name": "Transfer",
      "signature": "Transfer(address,address,uint256)",
      "topic0": "0xddf252ad...",
      "inputs": [
        {"name": "from", "type": "address", "indexed": true},
        {"name": "to", "type": "address", "indexed": true},
        {"name": "value", "type": "uint256", "indexed": false}
      ]
    }
  ],
  "security_flags": [],
  "sdk_enabled": true,
  "created_at": "2025-03-15T10:00:00Z"
}
```

## Project Categories

| Category | Description |
|---|---|
| DeFi | Decentralized finance protocols |
| Token | ERC-20, ERC-721, ERC-1155 tokens |
| Governance | DAO voting and governance |
| Bridge | Cross-chain bridge contracts |
| Utility | General utility contracts |
| Oracle | Price feeds and data oracles |
| NFT | Non-fungible token contracts |
| DAO | Decentralized autonomous organizations |
| SDK | Software development kits |
| Library | Reusable contract libraries |

## Security Flag Format

When the contract-watcher agent flags a dangerous pattern:

```json
{
  "abi_id": "abi_abc123",
  "pattern": "delegatecall",
  "severity": "CRITICAL",
  "location": "function upgradeProxy",
  "description": "Executes external code in caller context",
  "risk": "Complete fund drainage if target is malicious"
}
```

Flags are stored in `contract_security_flags` and displayed in the registry UI as warnings on the ABI detail page.

## SDK Generation

When an ABI is uploaded and SDK is enabled, the platform generates:

1. **Function descriptions** — human-readable descriptions of each function
2. **Usage examples** — code snippets showing how to call each function
3. **Parameter documentation** — type info, constraints, common values
4. **Event descriptions** — what each event means and when it fires

This SDK content is what powers CAG (Contract-Augmented Generation) — it gets embedded into the vector index so Groot can answer questions about specific contracts.

# SDK Gateway — MCP Tool API Reference

## Overview

The SDK Gateway exposes 4 MCP tools for deterministic, LLM-free access to smart contract SDKs.
All tools are available via REST (`POST /mcp/call`), GraphQL (`/mcp/gql`), SOAP (`/mcp/soap`), and WebSocket (`/mcp/ws`).

## Authentication

All calls require a valid JWT Bearer token with `inference:read` scope:
```
Authorization: Bearer <token>
```

## JSON-RPC 2.0 Format

All MCP tools can be called via standard JSON-RPC 2.0:

```json
{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "<tool_name>",
        "arguments": { ... }
    },
    "id": 1
}
```

---

## Tool 1: `resolve_contract`

Resolve a smart contract by name, slug, or address. Returns all deployment addresses across all chains.

### Request

```json
{
    "tool": "resolve_contract",
    "arguments": {
        "query": "USDC",
        "chain": "ethereum"
    }
}
```

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | yes | Contract name, slug (`user/contract`), or address (`0x...`) |
| `chain` | string | no | Filter to specific chain |

### Response

```json
{
    "result": [{
        "contract_name": "USDC",
        "slug": "circle/usdc",
        "description": "USD Coin stablecoin",
        "chain": "ethereum",
        "deployments": [
            {
                "chain": "ethereum",
                "chain_id": 1,
                "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "is_verified": true,
                "explorer_url": "https://etherscan.io"
            }
        ],
        "has_sdk": true,
        "contract_id": "uuid"
    }]
}
```

### Resolution Priority

1. **Address** (`0x...` prefix, 42+ chars) → exact match in `contract_repos.address`, then `contract_deployments.address`
2. **Slug** (contains `/`) → exact match in `contract_repos.slug`, then `registry_projects.slug`
3. **Name/keyword** → ILIKE search on `name`, `description`, `tags`

### curl Example

```bash
curl -s -X POST http://localhost:8000/mcp/call \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tool": "resolve_contract", "arguments": {"query": "staking"}}' | jq
```

---

## Tool 2: `fetch_sdk`

Fetch the full public SDK definition for a smart contract.

### Request (by chain + address)

```json
{
    "tool": "fetch_sdk",
    "arguments": {
        "chain": "ethereum",
        "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "include_abi": false
    }
}
```

### Request (by slug)

```json
{
    "tool": "fetch_sdk",
    "arguments": {
        "slug": "circle/usdc"
    }
}
```

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `chain` | string | no* | Blockchain name |
| `address` | string | no* | Contract address (`0x...`) |
| `slug` | string | no* | Contract slug (alternative to chain+address) |
| `include_abi` | boolean | no | Include raw ABI JSON (default: false) |

*Either `slug` OR `chain`+`address` must be provided.

### Response

```json
{
    "result": {
        "contract": {
            "name": "USDC",
            "slug": "circle/usdc",
            "chain": "ethereum",
            "address": "0xA0b8...",
            "description": "USD Coin stablecoin",
            "tags": ["defi", "stablecoin"],
            "language": "solidity",
            "is_verified": true
        },
        "functions": {
            "public": [
                {
                    "name": "transfer",
                    "signature": "transfer(address,uint256)",
                    "selector": "0xa9059cbb",
                    "mutability": "nonpayable",
                    "inputs": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}],
                    "outputs": [{"name": "", "type": "bool"}]
                }
            ],
            "owner_admin": [
                {
                    "name": "pause",
                    "signature": "pause()",
                    "access": "owner",
                    "warning": "RESTRICTED — requires owner access"
                }
            ]
        },
        "events": [
            {"name": "Transfer", "signature": "Transfer(address,address,uint256)"}
        ],
        "security_summary": {
            "total_functions": 12,
            "public_functions": 8,
            "admin_functions": 4,
            "dangerous_count": 0,
            "access_control_pattern": "role_based"
        },
        "sdk_version": "1.0.0",
        "sdk_hash": "abc123...",
        "generated_at": "2026-03-20T12:00:00Z",
        "deployments": [
            {"chain": "ethereum", "chain_id": 1, "address": "0xA0b8...", "is_verified": true}
        ]
    }
}
```

### Errors

| Error | Cause |
|-------|-------|
| `Public contract not found` | No public contract matches the query |
| `SDK not available for this contract` | Contract exists but SDK not generated |
| `Invalid SDK data` | Corrupted SDK JSON (run sync worker with --repair) |

---

## Tool 3: `list_chains_for_contract`

List all blockchain networks where a contract is deployed.

### Request

```json
{
    "tool": "list_chains_for_contract",
    "arguments": {
        "slug": "uniswap/router-v3"
    }
}
```

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `contract_id` | string | no* | Contract UUID |
| `slug` | string | no* | Contract slug |

*Either `contract_id` or `slug` required.

### Response

```json
{
    "result": [
        {
            "chain": "ethereum",
            "chain_id": 1,
            "chain_name": "Ethereum Mainnet",
            "address": "0x...",
            "currency": "ETH",
            "explorer_url": "https://etherscan.io",
            "is_verified": true
        }
    ]
}
```

---

## Tool 4: `bulk_sdk_export`

Paginated catalog of all public SDKs for agent discovery.

### Request

```json
{
    "tool": "bulk_sdk_export",
    "arguments": {
        "chain": "ethereum",
        "compact": true,
        "page": 1,
        "page_size": 50
    }
}
```

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `chain` | string | no | Filter by chain |
| `category` | string | no | Filter by tag/category |
| `compact` | boolean | no | Names+addresses only (default: true) |
| `page` | integer | no | Page number (default: 1) |
| `page_size` | integer | no | Results per page (default: 50, max: 200) |

### Response (compact)

```json
{
    "result": {
        "contracts": [
            {
                "name": "USDC",
                "slug": "circle/usdc",
                "chain": "ethereum",
                "address": "0xA0b8...",
                "description": "USD Coin stablecoin",
                "has_sdk": true,
                "public_function_count": 8,
                "admin_function_count": 4
            }
        ],
        "total": 42,
        "page": 1,
        "page_size": 50,
        "total_pages": 1
    }
}
```

Set `compact: false` to include full `functions`, `events`, and `security_summary` per contract.

---

## Agent Workflow Examples

### 1. Discover all available contracts

```
1. bulk_sdk_export(compact=true, page_size=200) → get full catalog
2. For each contract of interest: fetch_sdk(slug=...) → get full SDK
```

### 2. Find and call a specific function

```
1. resolve_contract(query="staking pool") → find contract addresses
2. fetch_sdk(chain="ethereum", address="0x...") → get function signatures
3. Use function signature + inputs to encode calldata client-side
```

### 3. Check multi-chain availability

```
1. resolve_contract(query="USDC") → see all deployments
2. list_chains_for_contract(slug="circle/usdc") → detailed chain info
```

---

## Error Handling

All errors return:
```json
{"error": "Human-readable error message"}
```

Common errors:
- `Unknown tool: <name>` — tool name misspelled
- `Missing required argument: <key>` — required param not provided
- `Public contract not found` — no matching public contract
- `SDK not available for this contract` — contract exists but SDK not generated

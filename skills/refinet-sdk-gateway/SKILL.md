---
name: refinet-sdk-gateway
description: >
  REFINET Cloud SDK Gateway skill for deterministic, LLM-free access to all
  public smart contract SDKs via MCP. Use this skill whenever the user or agent
  wants to: resolve contract addresses across chains, fetch public SDK definitions,
  list contract deployments per network, export the full SDK catalog, query
  contract functions without an LLM, bootstrap agent knowledge of available
  contracts, check SDK freshness, or automate SDK index maintenance. Triggers on
  phrases like "SDK gateway", "resolve contract", "fetch SDK", "contract address",
  "contract deployments", "SDK catalog", "public functions", "contract registry",
  "MCP SDK", "agent SDK access", "SDK index", "SDK sync", "bulk export",
  "contract lookup", "find contract", "which chains", "where deployed",
  "contract ABI", "SDK freshness", "stale SDK", "SDK worker", or any request
  to discover, lookup, fetch, or catalog smart contract SDKs on the
  GROOT-BETA / REFINET Cloud platform.
---

# REFINET SDK Gateway — Deterministic Contract SDK Access for Agents

This skill gives Claude and external agents everything needed to:
1. Resolve any public contract by name, slug, or address and get all deployment addresses across all chains
2. Fetch the full public SDK (functions, events, security summary) for any contract — no LLM required
3. List all chains where a contract is deployed
4. Export the complete SDK catalog for agent bootstrapping and discovery
5. Keep the SDK index fresh with automated sync workers and feedback loops

---

## Part 1 — Architecture

### 1.1 Design Principles

The SDK Gateway is **deterministic and LLM-free**. Every call is a pure database lookup that returns structured JSON. This means:
- **Instant response** — no inference latency, no token cost
- **Reproducible** — same query always returns same result (modulo DB state)
- **Agent-native** — structured JSON responses optimized for machine consumption
- **Two core calls** — `resolve_contract` (address/network) and `fetch_sdk` (SDK fetch)

### 1.2 Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     3 Data Sources                          │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Brain Layer   │  │ Chain Layer  │  │ Registry Layer   │  │
│  │              │  │              │  │                  │  │
│  │ contract_    │  │ contract_    │  │ registry_        │  │
│  │   repos      │  │  deployments │  │  projects        │  │
│  │ sdk_         │  │ supported_   │  │ registry_abis    │  │
│  │  definitions │  │  chains      │  │ registry_sdks    │  │
│  │ contract_    │  │              │  │                  │  │
│  │  functions   │  │              │  │                  │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         │                 │                    │            │
│         └─────────────────┼────────────────────┘            │
│                           │                                 │
│                    ┌──────▼───────┐                          │
│                    │ sdk_gateway  │                          │
│                    │   .py        │                          │
│                    └──────┬───────┘                          │
│                           │                                 │
│              ┌────────────┼────────────────┐                │
│              │            │                │                │
│        ┌─────▼─────┐ ┌───▼────┐  ┌────────▼────────┐       │
│        │ resolve_   │ │ fetch_ │  │ bulk_sdk_       │       │
│        │ contract   │ │  sdk   │  │  export         │       │
│        └─────┬──────┘ └───┬────┘  └────────┬────────┘       │
│              │            │                │                │
│              └────────────┼────────────────┘                │
│                           │                                 │
│                    ┌──────▼───────┐                          │
│                    │  MCP Gateway │                          │
│                    │ dispatch_    │                          │
│                    │  tool()      │                          │
│                    └──────┬───────┘                          │
│                           │                                 │
│         ┌─────────────────┼─────────────────┐               │
│         │                 │                 │               │
│    ┌────▼────┐     ┌──────▼──────┐   ┌──────▼──────┐       │
│    │  REST   │     │  GraphQL    │   │  WebSocket  │       │
│    │ /mcp/   │     │  /mcp/gql   │   │  /mcp/ws    │       │
│    │  call   │     │             │   │             │       │
│    └─────────┘     └─────────────┘   └─────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 Key Files

| Component | File |
|---|---|
| Service logic | `api/services/sdk_gateway.py` |
| MCP tool defs + dispatch | `api/services/mcp_gateway.py` |
| Event bus integration | `api/main.py` (lifespan) |
| Sync worker | `skills/refinet-sdk-gateway/scripts/sdk_sync_worker.py` |
| Index builder | `skills/refinet-sdk-gateway/scripts/sdk_indexer.py` |

### 1.4 Database Tables Used

| Table | Database | Purpose |
|---|---|---|
| `contract_repos` | public.db | Contract metadata, ABI, visibility |
| `sdk_definitions` | public.db | Generated SDK JSON blobs |
| `contract_functions` | public.db | Parsed functions with access control |
| `contract_deployments` | public.db | Multi-chain address mapping |
| `supported_chains` | public.db | Dynamic chain registry |
| `registry_projects` | public.db | Formal registry (fallback search) |

---

## Part 2 — MCP Tool Reference

### 2.1 `resolve_contract` — Contract Address / Network Lookup

**Purpose**: Find a contract by name, slug, or address and return all deployment addresses across all chains.

**Input**:
```json
{
    "query": "USDC",
    "chain": "ethereum"
}
```

- `query` (required): Contract name, slug (e.g. `circle/usdc`), or address (`0x...`)
- `chain` (optional): Filter results to a specific chain

**Output**:
```json
{
    "result": [{
        "contract_name": "USDC",
        "slug": "circle/usdc",
        "description": "USD Coin stablecoin",
        "chain": "ethereum",
        "deployments": [
            {"chain": "ethereum", "chain_id": 1, "address": "0xA0b8...", "is_verified": true, "explorer_url": "https://etherscan.io"},
            {"chain": "base", "chain_id": 8453, "address": "0x833...", "is_verified": true, "explorer_url": "https://basescan.org"}
        ],
        "has_sdk": true,
        "contract_id": "uuid-here"
    }]
}
```

**Resolution strategy** (in order):
1. Address match (`0x...` prefix) → `contract_repos.address` then `contract_deployments.address`
2. Slug match (contains `/`) → `contract_repos.slug` then `registry_projects.slug`
3. Name/keyword match → ILIKE on `name`, `description`, `tags`

**curl example**:
```bash
curl -X POST http://localhost:8000/mcp/call \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tool": "resolve_contract", "arguments": {"query": "staking"}}'
```

### 2.2 `fetch_sdk` — Public SDK Fetch

**Purpose**: Get the full public SDK for a contract. The primary agent API for understanding what a contract can do.

**Input** (one of two patterns):
```json
{"chain": "ethereum", "address": "0xA0b8..."}
```
or:
```json
{"slug": "circle/usdc"}
```

- `chain` + `address`: Direct deployment lookup
- `slug`: Slug-based lookup (alternative)
- `include_abi` (optional, default false): Include raw ABI JSON

**Output**:
```json
{
    "result": {
        "contract": {
            "name": "USDC",
            "slug": "circle/usdc",
            "chain": "ethereum",
            "address": "0xA0b8...",
            "description": "USD Coin stablecoin",
            "tags": ["defi", "stablecoin", "erc20"],
            "language": "solidity",
            "is_verified": true
        },
        "functions": {
            "public": [
                {"name": "transfer", "signature": "transfer(address,uint256)", "selector": "0xa9059cbb",
                 "inputs": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}],
                 "outputs": [{"name": "", "type": "bool"}], "mutability": "nonpayable"}
            ],
            "owner_admin": [
                {"name": "pause", "signature": "pause()", "access": "owner",
                 "warning": "RESTRICTED — requires owner access"}
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
        "sdk_hash": "sha256...",
        "generated_at": "2026-03-20T12:00:00Z",
        "deployments": [
            {"chain": "ethereum", "chain_id": 1, "address": "0xA0b8...", "is_verified": true}
        ]
    }
}
```

**curl example**:
```bash
curl -X POST http://localhost:8000/mcp/call \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tool": "fetch_sdk", "arguments": {"slug": "circle/usdc"}}'
```

### 2.3 `list_chains_for_contract` — Deployment Lookup

**Purpose**: Quick lookup — where is this contract deployed?

**Input**:
```json
{"slug": "uniswap/router-v3"}
```

**Output**:
```json
{
    "result": [
        {"chain": "ethereum", "chain_id": 1, "chain_name": "Ethereum Mainnet",
         "address": "0x...", "currency": "ETH", "explorer_url": "https://etherscan.io",
         "is_verified": true},
        {"chain": "polygon", "chain_id": 137, "chain_name": "Polygon",
         "address": "0x...", "currency": "MATIC", "explorer_url": "https://polygonscan.com",
         "is_verified": true}
    ]
}
```

### 2.4 `bulk_sdk_export` — SDK Catalog for Agent Bootstrapping

**Purpose**: Export all public SDKs as a paginated catalog. Agents use this to discover available contracts.

**Input**:
```json
{
    "chain": "ethereum",
    "compact": true,
    "page": 1,
    "page_size": 50
}
```

**Output (compact mode)**:
```json
{
    "result": {
        "contracts": [
            {"name": "USDC", "slug": "circle/usdc", "chain": "ethereum",
             "address": "0x...", "has_sdk": true,
             "public_function_count": 8, "admin_function_count": 4}
        ],
        "total": 42,
        "page": 1,
        "page_size": 50,
        "total_pages": 1
    }
}
```

Set `compact: false` to include full function signatures and security summaries (larger payloads).

---

## Part 3 — Automated Sync Worker

### 3.1 `sdk_sync_worker.py` — SDK Freshness Pipeline

**Location**: `skills/refinet-sdk-gateway/scripts/sdk_sync_worker.py`

**Schedule**: Cron every 6 hours or manual invocation.

**Pipeline**:

```
┌──────────────────┐
│ Staleness Scan   │ Compare ABI hash vs SDK generation hash
└────────┬─────────┘
         │
┌────────▼─────────┐
│ Missing SDK Scan │ Public contracts without SDK rows
└────────┬─────────┘
         │
┌────────▼─────────┐
│ Integrity Check  │ Verify sdk_hash matches sha256(sdk_json)
└────────┬─────────┘
         │
┌────────▼──────────┐
│ Auto-Regeneration │ (--repair flag) parse_abi → generate_sdk → update DB
└────────┬──────────┘
         │
┌────────▼─────────┐
│ Usage Analytics  │ Read sdk_queries.jsonl → top-10 hot contracts
└────────┬─────────┘
         │
┌────────▼─────────┐
│ Email Report     │ (--email flag) send via send_admin_alert()
└──────────────────┘
```

**Usage**:
```bash
# Dry-run scan — detect issues without fixing
python3 skills/refinet-sdk-gateway/scripts/sdk_sync_worker.py

# Auto-regenerate stale SDKs
python3 skills/refinet-sdk-gateway/scripts/sdk_sync_worker.py --repair

# Full cycle with email report
python3 skills/refinet-sdk-gateway/scripts/sdk_sync_worker.py --repair --email

# Invokable via MCP
POST /mcp/call {"tool": "execute_script", "arguments": {"script_name": "sdk_sync_worker"}}
```

### 3.2 Staleness Detection Algorithm

```python
# For each public contract with an SDK:
abi_hash_current = sha256(contract.abi_json)
sdk_abi_hash = sha256(abi_used_to_generate)  # derived from sdk_json metadata

if abi_hash_current != sdk_abi_hash:
    # SDK is stale — ABI was updated but SDK not regenerated
    mark_stale(contract)

if sha256(sdk.sdk_json) != sdk.sdk_hash:
    # Integrity failure — SDK data corrupted
    mark_corrupt(contract)
```

---

## Part 4 — SDK Indexer & Catalog

### 4.1 `sdk_indexer.py` — Catalog Builder

**Location**: `skills/refinet-sdk-gateway/scripts/sdk_indexer.py`

**Schedule**: Cron every 6 hours (offset 3h from sync worker) or manual.

**Output**: Writes `memory/working/sdk_catalog.json`

```json
{
    "generated_at": "2026-03-20T12:00:00Z",
    "total_contracts": 42,
    "total_sdks": 38,
    "chains": {
        "ethereum": {
            "chain_id": 1,
            "contract_count": 15,
            "contracts": [
                {"name": "USDC", "slug": "circle/usdc", "address": "0x...",
                 "function_count": 12, "sdk_hash": "sha256..."}
            ]
        },
        "base": { ... }
    },
    "top_queried": ["circle/usdc", "uniswap/router-v3"],
    "stale_count": 2
}
```

**Usage**:
```bash
python3 skills/refinet-sdk-gateway/scripts/sdk_indexer.py
python3 skills/refinet-sdk-gateway/scripts/sdk_indexer.py --output json
python3 skills/refinet-sdk-gateway/scripts/sdk_indexer.py --email
```

### 4.2 Cache Invalidation

The SDK catalog cache is invalidated via event bus when contracts change:

```python
# In api/main.py:
bus.subscribe("registry.sdk.*", invalidate_sdk_cache)
bus.subscribe("registry.abi.*", invalidate_sdk_cache)
bus.subscribe("registry.visibility.*", invalidate_sdk_cache)
```

The `bulk_sdk_export` MCP tool always queries live DB (no stale cache risk). The cached `sdk_catalog.json` is used only by the indexer for offline analysis and reporting.

---

## Part 5 — Feedback Loop & Analytics

### 5.1 Usage Tracking

Every `resolve_contract` and `fetch_sdk` call appends to `memory/working/sdk_queries.jsonl`:

```jsonl
{"ts":"2026-03-20T12:00:00Z","cid":"contract-uuid","tool":"resolve_contract"}
{"ts":"2026-03-20T12:01:00Z","cid":"contract-uuid","tool":"fetch_sdk"}
```

### 5.2 Feedback Loop Architecture

```
Agent calls resolve_contract / fetch_sdk
    │
    ├──→ _log_sdk_query() appends to sdk_queries.jsonl
    │
    ▼
sdk_sync_worker.py (cron 6h)
    │
    ├── Reads sdk_queries.jsonl → aggregates hot contracts
    ├── Detects stale SDKs (ABI hash mismatch)
    ├── Auto-regenerates (--repair)
    ├── Reports via email (--email)
    └── Prunes old entries (>30 days)
    │
    ▼
sdk_indexer.py (cron 6h, offset 3h)
    │
    ├── Rebuilds sdk_catalog.json
    ├── Ranks contracts by query frequency
    └── Reports chain-by-chain summary
```

### 5.3 Hot Contract Detection

The sync worker aggregates usage from `sdk_queries.jsonl` to identify the most-queried contracts. This data is included in:
- Email reports (top-10 hot contracts)
- The SDK catalog (`top_queried` field)
- Worker stdout for monitoring

---

## Part 6 — Operating Procedures

### When user asks: "Check SDK status"

```bash
DATABASE_PATH=data/public.db python3 skills/refinet-sdk-gateway/scripts/sdk_sync_worker.py
```

Reports: total SDKs, stale count, missing count, integrity errors, top-queried contracts.

### When user asks: "Refresh all SDKs"

```bash
DATABASE_PATH=data/public.db python3 skills/refinet-sdk-gateway/scripts/sdk_sync_worker.py --repair
```

Auto-regenerates any stale or missing SDKs.

### When user asks: "Export SDK catalog"

Use the `bulk_sdk_export` MCP tool:
```json
{"tool": "bulk_sdk_export", "arguments": {"compact": false, "page_size": 200}}
```

Or build the offline catalog:
```bash
DATABASE_PATH=data/public.db python3 skills/refinet-sdk-gateway/scripts/sdk_indexer.py --output json
```

### When user asks: "Find contract X" or "Where is X deployed?"

Use `resolve_contract`:
```json
{"tool": "resolve_contract", "arguments": {"query": "X"}}
```

### When user asks: "Get SDK for contract X"

Use `fetch_sdk`:
```json
{"tool": "fetch_sdk", "arguments": {"slug": "owner/X"}}
```
or:
```json
{"tool": "fetch_sdk", "arguments": {"chain": "ethereum", "address": "0x..."}}
```

### When user asks: "Debug missing SDK"

1. Check if contract exists and is public: `resolve_contract` → verify `has_sdk: false`
2. Check if ABI is parsed: look at contract `status` field
3. If status is `draft`, user needs to trigger parse: `POST /repo/contracts/{slug}/parse`
4. If status is `parsed` but no SDK, run sync worker with `--repair`

---

## Part 7 — Safety Constraints

### Access Control

- **Only `is_public=True` SDKs are exposed** — private contracts are never returned
- **Source code is NEVER included** — only parsed SDK definitions
- **ABI is opt-in** — only included when `include_abi: true` is explicitly requested
- **No LLM in the path** — all responses are deterministic DB lookups

### Rate Limiting

- `bulk_sdk_export` is capped at 200 results per page
- Usage tracking is fire-and-forget (never blocks the response)
- JSONL logs are pruned after 30 days by the sync worker

### Data Integrity

- `sdk_hash` is verified on every sync worker run
- Stale SDKs are detected by comparing ABI hash at generation time vs current
- Corrupted SDK JSON is flagged and excluded from responses

### Event-Driven Freshness

- SDK catalog cache is invalidated on any `registry.sdk.*`, `registry.abi.*`, or `registry.visibility.*` event
- The sync worker can be triggered manually or via cron
- No stale data is served — `fetch_sdk` and `resolve_contract` always query live DB

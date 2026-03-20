# REFINET Chain Listener API Reference

## Chain Listener Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/chain/listeners` | JWT | Create a new event listener |
| `GET` | `/chain/listeners` | JWT | List all active listeners |
| `GET` | `/chain/listeners/{id}` | JWT | Get listener details and status |
| `PUT` | `/chain/listeners/{id}` | JWT | Update listener filters |
| `DELETE` | `/chain/listeners/{id}` | JWT | Deactivate listener |
| `GET` | `/chain/events` | JWT | Query captured events (filtered) |
| `GET` | `/chain/events/{id}` | JWT | Get single event with decoded params |
| `POST` | `/chain/events/{id}/interpret` | JWT | Request agent interpretation of event |

## Create Listener Request

```json
{
  "chain_id": 1,
  "contract_address": "0x1234...abcd",
  "event_signatures": [
    "Transfer(address,address,uint256)",
    "Approval(address,address,uint256)"
  ],
  "webhook_url": "https://api.refinet.io/webhooks/chain-event",
  "from_block": "latest",
  "label": "USDC transfers"
}
```

## Captured Event Schema

```json
{
  "id": "evt_abc123",
  "listener_id": "lst_def456",
  "chain_id": 1,
  "contract_address": "0x1234...abcd",
  "tx_hash": "0xabcd...1234",
  "block_number": 19500000,
  "block_timestamp": "2025-03-15T10:30:00Z",
  "event_signature": "Transfer(address,address,uint256)",
  "raw_data": "0x...",
  "decoded_params": {
    "from": "0xsender...",
    "to": "0xreceiver...",
    "value": "1000000000000000000"
  },
  "status": "raw",
  "interpretation": null,
  "classification": null,
  "created_at": "2025-03-15T10:30:05Z"
}
```

## Event Status Lifecycle

```
raw → processing → interpreted → (alerted)
                              └→ archived
```

## Chain RPC Configuration

```yaml
# configs/chains.yaml
chains:
  ethereum:
    chain_id: 1
    rpc_urls:
      - https://eth.llamarpc.com
      - https://rpc.ankr.com/eth
    block_time_seconds: 12
    confirmations: 3

  polygon:
    chain_id: 137
    rpc_urls:
      - https://polygon-rpc.com
      - https://rpc.ankr.com/polygon
    block_time_seconds: 2
    confirmations: 5

  arbitrum:
    chain_id: 42161
    rpc_urls:
      - https://arb1.arbitrum.io/rpc
      - https://rpc.ankr.com/arbitrum
    block_time_seconds: 0.25
    confirmations: 1

  optimism:
    chain_id: 10
    rpc_urls:
      - https://mainnet.optimism.io
      - https://rpc.ankr.com/optimism
    block_time_seconds: 2
    confirmations: 1

  base:
    chain_id: 8453
    rpc_urls:
      - https://mainnet.base.org
      - https://rpc.ankr.com/base
    block_time_seconds: 2
    confirmations: 1

  sepolia:
    chain_id: 11155111
    rpc_urls:
      - https://rpc.sepolia.org
      - https://rpc.ankr.com/eth_sepolia
    block_time_seconds: 12
    confirmations: 2
```

All RPCs are public and free — no API keys required. The chain listener rotates between URLs on failure.

## Database Schema

### chain_listeners
```sql
CREATE TABLE chain_listeners (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    chain_id INTEGER NOT NULL,
    contract_address TEXT NOT NULL,
    event_signatures JSON,
    webhook_url TEXT,
    from_block TEXT DEFAULT 'latest',
    label TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    last_block_processed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### chain_events
```sql
CREATE TABLE chain_events (
    id TEXT PRIMARY KEY,
    listener_id TEXT REFERENCES chain_listeners(id),
    chain_id INTEGER NOT NULL,
    contract_address TEXT NOT NULL,
    tx_hash TEXT NOT NULL,
    block_number INTEGER NOT NULL,
    block_timestamp TIMESTAMP,
    event_signature TEXT,
    raw_data TEXT,
    decoded_params JSON,
    status TEXT DEFAULT 'raw',
    interpretation TEXT,
    classification TEXT,
    risk_level TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### contract_security_flags
```sql
CREATE TABLE contract_security_flags (
    id TEXT PRIMARY KEY,
    abi_id TEXT REFERENCES contract_abis(id),
    pattern TEXT NOT NULL,
    severity TEXT NOT NULL,
    location TEXT,
    description TEXT,
    risk TEXT,
    flagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

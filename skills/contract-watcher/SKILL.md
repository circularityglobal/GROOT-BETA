---
name: refinet-contract-watcher
description: >
  REFINET Cloud contract watcher skill for autonomous on-chain intelligence,
  smart contract security analysis, and blockchain event monitoring. Use this
  skill whenever the user wants to: monitor on-chain events, analyze smart
  contract ABIs for dangerous operations, track contract activity across chains,
  interpret blockchain events in context, detect bridge transactions, audit
  contract security, correlate cross-chain events, monitor starred/forked
  contracts, flag delegatecall/selfdestruct patterns, or build autonomous
  blockchain monitoring workflows on REFINET Cloud. Triggers on phrases like
  "contract watcher", "chain events", "on-chain monitoring", "ABI security",
  "dangerous functions", "delegatecall", "selfdestruct", "bridge detection",
  "cross-chain", "contract activity", "chain listener", "event interpretation",
  "smart contract audit", "contract security scan", "blockchain alerts",
  "chain intelligence", "token transfer monitoring", "governance vote tracking",
  "contract watcher agent", "on-chain anomaly", "registry security", "EVM events",
  or any request to monitor, analyze, audit, or automate blockchain activity
  on the GROOT-BETA / REFINET Cloud platform. Also triggers when discussing
  contract ABIs, event signatures, function selectors, or multi-chain monitoring
  across Ethereum, Polygon, Arbitrum, Optimism, Base, or Sepolia.
---

# REFINET Contract Watcher — Autonomous On-Chain Intelligence Skill

This skill gives Claude everything needed to:
1. Interpret blockchain events in real time using the contract's ABI and SDK context
2. Automatically scan new ABI uploads for dangerous operations and flag them
3. Monitor starred/forked contracts for activity anomalies across 6 EVM chains
4. Correlate cross-chain events (bridge transfers, multi-chain governance)
5. Send structured admin alerts for security flags, anomalies, and weekly chain intelligence reports

---

## Part 1 — On-Chain Architecture

### 1.1 The Chain Listener System

REFINET's chain listener monitors EVM-compatible chains for events matching configured filters.

```
Block produced on chain
    │
    ▼
Chain Listener (polling + WebSocket)
    │
    ├── Filter: contract address match?
    ├── Filter: event signature match?
    └── Filter: chain ID match?
    │
    ▼ (if matched)
Event captured → stored in chain_events table
    │
    ├──→ Webhook fired (if configured)
    ├──→ Trigger Router → contract-watcher agent
    └──→ Raw event stored for audit trail
```

### 1.2 Supported Chains

| Chain | Chain ID | RPC Source | Status |
|---|---|---|---|
| Ethereum Mainnet | 1 | Public RPC / Infura free | Production |
| Polygon | 137 | Public RPC | Production |
| Arbitrum One | 42161 | Public RPC | Production |
| Optimism | 10 | Public RPC | Production |
| Base | 8453 | Public RPC | Production |
| Sepolia (testnet) | 11155111 | Public RPC | Testing |

### 1.3 Storage Architecture

| Component | Storage | Location |
|---|---|---|
| Event listeners | SQLite `public.db` | `chain_listeners` table |
| Captured events | SQLite `public.db` | `chain_events` table |
| Contract ABIs | SQLite `public.db` | `contract_abis` table |
| Parsed functions | SQLite `public.db` | `abi_functions` table |
| Parsed events | SQLite `public.db` | `abi_events` table |
| Security flags | SQLite `public.db` | `contract_security_flags` table |
| Registry projects | SQLite `public.db` | `registry_projects` table |
| Stars/forks | SQLite `public.db` | `registry_stars`, `registry_forks` tables |

### 1.4 Dangerous Operation Patterns

These patterns are flagged automatically when an ABI is uploaded. They represent operations that can cause irreversible harm if misused.

| Pattern | Severity | Description |
|---|---|---|
| `delegatecall` | CRITICAL | Executes external code in caller's context — can drain all funds |
| `selfdestruct` | CRITICAL | Permanently destroys the contract and sends remaining ETH |
| `tx.origin` | HIGH | Authentication bypass — phishing attacks can exploit this |
| `call.value` (unchecked) | HIGH | Ether transfer without return value check — reentrancy risk |
| `assembly { ... }` | MEDIUM | Inline assembly bypasses Solidity safety checks |
| `block.timestamp` | LOW | Miner-manipulable — risky for time-sensitive logic |
| `ecrecover` | MEDIUM | Signature verification — vulnerable if nonce not checked |
| Proxy patterns | MEDIUM | Upgradeable contracts can change behavior post-deploy |
| Ownership transfer | MEDIUM | `transferOwnership` / `renounceOwnership` changes control |
| Infinite approval | HIGH | `approve(spender, type(uint256).max)` — unlimited token access |

---

## Part 2 — Autonomous Pipelines

### 2.1 Real-Time Event Interpretation

When the chain listener captures an event, the contract-watcher agent interprets it:

```
1. PERCEIVE — New event from chain_events (trigger: on-chain or webhook)
2. PLAN    — Load contract ABI + SDK from registry, identify event signature
3. ACT     — Decode event parameters, classify event type, check against patterns
4. OBSERVE — Determine: routine / notable / anomalous / dangerous
5. REFLECT — Compare against historical patterns in episodic memory
6. STORE   — Log interpretation, send alert if anomalous/dangerous
```

**Event classification logic:**

```python
EVENT_CLASSIFICATIONS = {
    "routine": {
        "description": "Normal contract operation",
        "examples": ["Transfer (small amount)", "Approval (known spender)", "Deposit"],
        "action": "log_only"
    },
    "notable": {
        "description": "Significant but expected operation",
        "examples": ["Large transfer (>1% supply)", "New governance proposal", "Ownership change"],
        "action": "log_and_digest"
    },
    "anomalous": {
        "description": "Unexpected pattern detected",
        "examples": ["Transfer to known exploit address", "Rapid repeated calls", "Unusual gas usage"],
        "action": "alert_admin"
    },
    "dangerous": {
        "description": "Potentially destructive operation",
        "examples": ["selfdestruct called", "delegatecall to unknown", "Ownership renounced"],
        "action": "alert_admin_critical"
    }
}
```

### 2.2 New ABI Security Analysis

When a contract ABI is uploaded via `POST /registry/projects/{id}/abis`:

```python
DANGEROUS_PATTERNS = {
    "delegatecall": {
        "severity": "CRITICAL",
        "regex": r"delegatecall",
        "description": "Executes external code in caller context",
        "risk": "Complete fund drainage if target is malicious"
    },
    "selfdestruct": {
        "severity": "CRITICAL",
        "regex": r"selfdestruct|SELFDESTRUCT",
        "description": "Permanently destroys contract",
        "risk": "Irreversible loss of contract state and funds"
    },
    "tx_origin": {
        "severity": "HIGH",
        "regex": r"tx\.origin",
        "description": "Uses tx.origin for authentication",
        "risk": "Phishing attacks can bypass authentication"
    },
    "unchecked_call": {
        "severity": "HIGH",
        "regex": r"\.call\{value:",
        "description": "Low-level call with value transfer",
        "risk": "Reentrancy if return value not checked"
    },
    "infinite_approval": {
        "severity": "HIGH",
        "regex": r"type\(uint256\)\.max|0xffffffff",
        "description": "Unlimited token approval",
        "risk": "Spender can drain all approved tokens"
    },
    "inline_assembly": {
        "severity": "MEDIUM",
        "regex": r"assembly\s*\{",
        "description": "Inline assembly usage",
        "risk": "Bypasses Solidity safety checks"
    },
    "proxy_pattern": {
        "severity": "MEDIUM",
        "regex": r"upgradeTo|_implementation|delegatecall.*implementation",
        "description": "Upgradeable proxy pattern detected",
        "risk": "Contract behavior can change post-deployment"
    },
    "ownership_transfer": {
        "severity": "MEDIUM",
        "regex": r"transferOwnership|renounceOwnership",
        "description": "Ownership control function",
        "risk": "Contract control can be transferred or abandoned"
    }
}


def analyze_abi_security(abi_json: list, source_code: str = None) -> dict:
    """Analyze an ABI (and optionally source code) for dangerous patterns."""
    flags = []

    # 1. Check ABI function signatures
    for item in abi_json:
        if item.get("type") == "function":
            name = item.get("name", "")
            # Check for dangerous function names
            if name in ("selfdestruct", "delegatecall", "suicide"):
                flags.append({
                    "pattern": name,
                    "severity": "CRITICAL",
                    "location": f"function {name}",
                    "description": DANGEROUS_PATTERNS.get(name, {}).get("description", "Dangerous function")
                })

            # Check for ownership-related functions
            if name in ("transferOwnership", "renounceOwnership"):
                flags.append({
                    "pattern": "ownership_transfer",
                    "severity": "MEDIUM",
                    "location": f"function {name}",
                    "description": "Ownership control function detected"
                })

            # Check for approval patterns
            if name == "approve":
                flags.append({
                    "pattern": "approval",
                    "severity": "LOW",
                    "location": f"function {name}",
                    "description": "Token approval function — check for infinite approval usage"
                })

    # 2. If source code available, scan with regex patterns
    if source_code:
        import re
        for pattern_name, pattern_info in DANGEROUS_PATTERNS.items():
            matches = re.findall(pattern_info["regex"], source_code)
            if matches:
                flags.append({
                    "pattern": pattern_name,
                    "severity": pattern_info["severity"],
                    "location": f"{len(matches)} occurrences in source",
                    "description": pattern_info["description"],
                    "risk": pattern_info["risk"]
                })

    # 3. Compute overall risk score
    severity_weights = {"CRITICAL": 10, "HIGH": 5, "MEDIUM": 2, "LOW": 1}
    risk_score = sum(severity_weights.get(f["severity"], 0) for f in flags)

    return {
        "flags": flags,
        "flag_count": len(flags),
        "risk_score": risk_score,
        "risk_level": (
            "CRITICAL" if risk_score >= 10 else
            "HIGH" if risk_score >= 5 else
            "MEDIUM" if risk_score >= 2 else
            "LOW" if risk_score >= 1 else
            "CLEAN"
        ),
        "critical_count": sum(1 for f in flags if f["severity"] == "CRITICAL"),
        "high_count": sum(1 for f in flags if f["severity"] == "HIGH"),
        "medium_count": sum(1 for f in flags if f["severity"] == "MEDIUM"),
    }
```

### 2.3 Contract Activity Monitoring

For starred and forked contracts, monitor on-chain activity periodically.

```python
def get_watched_contracts(db) -> list[dict]:
    """Get all contracts that have been starred or forked in the registry."""
    return db.execute("""
        SELECT DISTINCT ca.contract_address, ca.chain_id, rp.name as project_name,
               COUNT(DISTINCT rs.user_id) as star_count,
               COUNT(DISTINCT rf.user_id) as fork_count
        FROM contract_abis ca
        JOIN registry_projects rp ON rp.id = ca.project_id
        LEFT JOIN registry_stars rs ON rs.project_id = rp.id
        LEFT JOIN registry_forks rf ON rf.project_id = rp.id
        GROUP BY ca.contract_address, ca.chain_id
        HAVING star_count > 0 OR fork_count > 0
        ORDER BY star_count + fork_count DESC
    """).fetchall()


def check_contract_activity(contract_address: str, chain_id: int) -> dict:
    """Check recent activity for a specific contract via RPC."""
    # This calls the chain's RPC endpoint to check:
    # 1. Recent transaction count (eth_getTransactionCount)
    # 2. Current balance (eth_getBalance)
    # 3. Recent events (eth_getLogs with block range)
    #
    # Implementation uses the chain listener's RPC configuration
    # No external API keys needed — public RPCs only
    pass


def detect_activity_anomalies(current: dict, historical: list[dict]) -> list[dict]:
    """Compare current activity against historical baselines from episodic memory."""
    anomalies = []

    if not historical:
        return anomalies  # No baseline yet — first run

    # Calculate baseline averages from last 7 entries
    avg_tx_count = sum(h.get("tx_count", 0) for h in historical[-7:]) / min(len(historical), 7)
    avg_balance = sum(h.get("balance_eth", 0) for h in historical[-7:]) / min(len(historical), 7)

    # Check for transaction spike (>3x baseline)
    if current.get("tx_count", 0) > avg_tx_count * 3 and avg_tx_count > 0:
        anomalies.append({
            "type": "tx_spike",
            "severity": "HIGH",
            "detail": f"Transaction count {current['tx_count']} vs baseline {avg_tx_count:.0f}",
            "multiplier": round(current["tx_count"] / avg_tx_count, 1)
        })

    # Check for large balance change (>50% decrease)
    if avg_balance > 0 and current.get("balance_eth", 0) < avg_balance * 0.5:
        anomalies.append({
            "type": "balance_drop",
            "severity": "CRITICAL",
            "detail": f"Balance dropped to {current['balance_eth']:.4f} ETH from avg {avg_balance:.4f} ETH",
            "pct_change": round((current["balance_eth"] - avg_balance) / avg_balance * 100, 1)
        })

    # Check for balance surge (>5x baseline)
    if current.get("balance_eth", 0) > avg_balance * 5 and avg_balance > 0:
        anomalies.append({
            "type": "balance_surge",
            "severity": "MEDIUM",
            "detail": f"Balance surged to {current['balance_eth']:.4f} ETH from avg {avg_balance:.4f} ETH",
            "multiplier": round(current["balance_eth"] / avg_balance, 1)
        })

    return anomalies
```

### 2.4 Cross-Chain Event Correlation

Detect and verify bridge transactions that span multiple chains.

```python
KNOWN_BRIDGE_CONTRACTS = {
    # Canonical bridges — addresses per chain
    "optimism_bridge": {
        1: "0x99C9fc46f92E8a1c0deC1b1747d010903E884bE1",     # L1 bridge
        10: "0x4200000000000000000000000000000000000010",       # L2 bridge
    },
    "arbitrum_bridge": {
        1: "0x8315177aB297bA92A06054cE80a67Ed4DBd7ed3a",      # L1 bridge
        42161: "0x0000000000000000000000000000000000000064",    # L2 bridge
    },
    "base_bridge": {
        1: "0x3154Cf16ccdb4C6d922629664174b904d80F2C35",      # L1 bridge
        8453: "0x4200000000000000000000000000000000000010",     # L2 bridge
    },
    "polygon_bridge": {
        1: "0xA0c68C638235ee32657e8f720a23ceC1bFc77C77",      # L1 bridge
        137: "0x0000000000000000000000000000000000001010",      # L2 bridge
    }
}


def correlate_bridge_events(events: list[dict]) -> list[dict]:
    """Find bridge deposit/withdrawal pairs across chains."""
    correlations = []

    # Group events by bridge contract
    bridge_events = {}
    for event in events:
        contract = event.get("contract_address", "").lower()
        for bridge_name, addresses in KNOWN_BRIDGE_CONTRACTS.items():
            for chain_id, addr in addresses.items():
                if contract == addr.lower() and event.get("chain_id") == chain_id:
                    if bridge_name not in bridge_events:
                        bridge_events[bridge_name] = []
                    bridge_events[bridge_name].append(event)

    # For each bridge, look for L1→L2 deposit / L2→L1 withdrawal pairs
    for bridge_name, bevents in bridge_events.items():
        l1_events = [e for e in bevents if e["chain_id"] == 1]
        l2_events = [e for e in bevents if e["chain_id"] != 1]

        for l1 in l1_events:
            for l2 in l2_events:
                # Match by amount, sender, or cross-reference hash
                if (l1.get("value") == l2.get("value") and
                    l1.get("from_address") == l2.get("to_address")):
                    correlations.append({
                        "bridge": bridge_name,
                        "direction": "L1→L2",
                        "l1_chain": 1,
                        "l2_chain": l2["chain_id"],
                        "l1_tx": l1.get("tx_hash"),
                        "l2_tx": l2.get("tx_hash"),
                        "amount": l1.get("value"),
                        "sender": l1.get("from_address"),
                        "verified": True
                    })

    return correlations
```

---

## Part 3 — Admin Email Notifications

### 3.1 Alert Categories

| Category | Subject Prefix | When |
|---|---|---|
| ABI_SECURITY | `[REFINET CHAIN]` | New ABI uploaded — security analysis results |
| EVENT_ANOMALY | `[REFINET CHAIN]` | On-chain event classified as anomalous or dangerous |
| ACTIVITY_ALERT | `[REFINET CHAIN]` | Watched contract shows unusual activity pattern |
| BRIDGE_ALERT | `[REFINET CHAIN]` | Bridge transaction detected — correlation result |
| WEEKLY_REPORT | `[REFINET CHAIN]` | Weekly chain intelligence digest |

### 3.2 Security Analysis Email Template

```python
def abi_security_email_body(project_name: str, analysis: dict) -> str:
    risk_colors = {
        "CRITICAL": "#ff4444", "HIGH": "#ff6b6b",
        "MEDIUM": "#ffd93d", "LOW": "#00d4aa", "CLEAN": "#00d4aa"
    }
    risk_color = risk_colors.get(analysis["risk_level"], "#888")

    flag_rows = ""
    for f in analysis["flags"]:
        sev_color = risk_colors.get(f["severity"], "#888")
        flag_rows += f"""
        <tr style="border-bottom: 1px solid #2a2a4a;">
          <td style="padding: 8px; color: {sev_color}; font-weight: bold;">{f['severity']}</td>
          <td style="padding: 8px;">{f['pattern']}</td>
          <td style="padding: 8px; color: #ccc;">{f['description']}</td>
        </tr>"""

    return f"""
    <div style="background: {'#2a1a1a' if analysis['risk_level'] in ('CRITICAL','HIGH') else '#1a2a2a'}; border-left: 4px solid {risk_color}; padding: 12px; margin: 8px 0; border-radius: 4px;">
      <p style="margin: 0; color: {risk_color}; font-size: 16px; font-weight: bold;">
        Risk level: {analysis['risk_level']} (score: {analysis['risk_score']})
      </p>
      <p style="margin: 4px 0 0; color: #888;">Project: {project_name}</p>
    </div>
    <table style="width: 100%; border-collapse: collapse; color: #e0e0e0; margin-top: 12px;">
      <tr style="border-bottom: 2px solid #333;">
        <th style="padding: 8px; text-align: left;">Severity</th>
        <th style="padding: 8px; text-align: left;">Pattern</th>
        <th style="padding: 8px; text-align: left;">Description</th>
      </tr>
      {flag_rows}
    </table>
    <p style="color: #888; font-size: 13px; margin-top: 12px;">
      {analysis['flag_count']} flags: {analysis['critical_count']} critical, {analysis['high_count']} high, {analysis['medium_count']} medium
    </p>
    """
```

### 3.3 Weekly Chain Intelligence Template

```python
def weekly_chain_report_body(stats: dict) -> str:
    return f"""
    <div style="display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px;">
      <div style="flex: 1; min-width: 110px; background: #1a2a4e; padding: 12px; border-radius: 6px; text-align: center;">
        <div style="font-size: 24px; color: #00d4aa; font-weight: bold;">{stats.get('contracts_monitored', 0)}</div>
        <div style="font-size: 12px; color: #888;">Monitored</div>
      </div>
      <div style="flex: 1; min-width: 110px; background: #1a2a4e; padding: 12px; border-radius: 6px; text-align: center;">
        <div style="font-size: 24px; color: #00d4aa; font-weight: bold;">{stats.get('events_captured', 0)}</div>
        <div style="font-size: 12px; color: #888;">Events</div>
      </div>
      <div style="flex: 1; min-width: 110px; background: #1a2a4e; padding: 12px; border-radius: 6px; text-align: center;">
        <div style="font-size: 24px; color: {'#ff6b6b' if stats.get('security_flags', 0) > 0 else '#00d4aa'}; font-weight: bold;">{stats.get('security_flags', 0)}</div>
        <div style="font-size: 12px; color: #888;">Flags</div>
      </div>
      <div style="flex: 1; min-width: 110px; background: #1a2a4e; padding: 12px; border-radius: 6px; text-align: center;">
        <div style="font-size: 24px; color: #00d4aa; font-weight: bold;">{stats.get('bridge_txs', 0)}</div>
        <div style="font-size: 12px; color: #888;">Bridge TXs</div>
      </div>
    </div>
    <table style="width: 100%; color: #e0e0e0; font-size: 13px;">
      <tr><td style="padding: 4px 0; color: #888;">New ABIs analyzed</td><td style="text-align: right;">{stats.get('abis_analyzed', 0)}</td></tr>
      <tr><td style="padding: 4px 0; color: #888;">Critical flags</td><td style="text-align: right; color: {'#ff6b6b' if stats.get('critical_flags', 0) > 0 else '#00d4aa'};">{stats.get('critical_flags', 0)}</td></tr>
      <tr><td style="padding: 4px 0; color: #888;">Anomalous events</td><td style="text-align: right;">{stats.get('anomalous_events', 0)}</td></tr>
      <tr><td style="padding: 4px 0; color: #888;">Chains active</td><td style="text-align: right;">{stats.get('chains_active', 0)}/6</td></tr>
      <tr><td style="padding: 4px 0; color: #888;">Avg block latency</td><td style="text-align: right;">{stats.get('avg_block_latency_ms', '—')}ms</td></tr>
    </table>
    """
```

---

## Part 4 — Cron Schedule

```yaml
# configs/contract-watcher-cron.yaml
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

  # Every 15 minutes — check for new ABI uploads
  - name: abi-security-scan
    interval: 15m
    agent: contract-watcher
    task: >
      Check contract_abis table for ABIs uploaded since last scan that
      have not been security-analyzed. For each, run analyze_abi_security.
      Flag dangerous patterns in the registry. Email admin security
      assessment for any ABI with risk_level HIGH or CRITICAL.

  # Every 4 hours — watched contract activity check
  - name: activity-monitor
    interval: 4h
    agent: contract-watcher
    task: >
      Get all starred/forked contracts from the registry. For each,
      check on-chain activity via public RPC (tx count, balance, recent logs).
      Compare against historical baselines in episodic memory. Alert admin
      if anomalies detected (tx spike >3x, balance drop >50%, balance surge >5x).

  # Every 12 hours — cross-chain bridge correlation
  - name: bridge-correlation
    interval: 12h
    agent: contract-watcher
    task: >
      Scan recent chain_events for transactions involving known bridge
      contracts across all 6 supported chains. Correlate L1 deposits
      with L2 arrivals. Flag any unmatched deposits (funds sent but
      not received). Report bridge activity summary.

  # Weekly on Monday at 06:30 UTC — chain intelligence report
  - name: weekly-report
    cron: "30 6 * * 1"
    agent: contract-watcher
    task: >
      Compile weekly chain intelligence report: total contracts monitored,
      events captured per chain, security flags raised (by severity),
      anomalous events detected, bridge transactions correlated, new ABIs
      analyzed, chains active vs inactive. Format as HTML dashboard
      email and send to admin.
```

---

## Part 5 — Operating Procedures

### 5.1 When User Asks to Scan a Contract

1. Accept contract address and chain ID
2. Fetch ABI from registry (or from on-chain if not in registry)
3. Run `analyze_abi_security()` against ABI and source (if available)
4. Report all flags with severity, pattern, and risk description
5. If risk_level is HIGH or CRITICAL, email admin immediately
6. Store analysis in episodic memory

### 5.2 When User Asks About Chain Events

1. Query `chain_events` for the specified contract/chain/time range
2. Decode each event using the contract's ABI from the registry
3. Classify each event using EVENT_CLASSIFICATIONS
4. Present summary: event counts by type, any anomalies flagged
5. Compare against historical patterns if available

### 5.3 When User Asks to Set Up Monitoring

1. Verify contract exists in the registry (or offer to add it)
2. Create chain listener via `POST /chain/listeners`
3. Configure event filters (specific events or all events)
4. Set up webhook callback for real-time processing
5. Run initial activity baseline check
6. Email admin confirming monitoring activation

### 5.4 When User Asks About Bridge Activity

1. Query recent events for all known bridge contracts
2. Run `correlate_bridge_events()` to match L1↔L2 pairs
3. Flag any unmatched deposits (sent but not received)
4. Report correlation results with TX hashes

---

## Part 6 — Safety Constraints

Inherited from SAFETY.md — always enforced:

- Never execute financial transactions or sign blockchain transactions without explicit user confirmation
- Never call contract functions classified as dangerous without user approval
- Never expose smart contract source code — SDKs and parsed ABIs only
- Display clear warnings when an action involves financial risk
- Log all tool calls to episodic memory with full parameters and results
- Contract analysis is read-only — the agent observes and reports, never executes
- Max delegation depth: 3 (can delegate to knowledge-curator for contract docs)

---

## Part 7 — Reference Files

Read these for implementation specifics:

- `references/chain-api.md` — Chain listener API endpoints, event schemas, RPC configuration
- `references/registry-api.md` — Smart contract registry API, ABI schemas, security flag format

For platform infrastructure context, consult the `refinet-platform-ops` skill.
For knowledge base integration (CAG sync), consult the `refinet-knowledge-curator` skill.
For agent architecture patterns, consult the `agent-os` skill.

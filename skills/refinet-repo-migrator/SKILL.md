---
name: refinet-repo-migrator
description: >
  REFINET Cloud repository migrator skill for autonomous GitHub-to-REFINET smart
  contract migration. Use this skill whenever the user wants to: import contracts
  from a GitHub repo, migrate smart contracts to REFINET, pull Solidity files from
  GitHub, parse ABIs from source code, import a GitHub project into the contract
  registry, convert .sol files to ABI format, generate SDKs from GitHub contracts,
  migrate a DeFi protocol's contracts, import token contracts, clone a repo's
  contracts into GROOT Brain, process Solidity/Vyper/Rust/Move/Bitcoin/Solana/Hedera
  /XRPL/Algorand/XLM contract files from GitHub, or build automated contract
  ingestion pipelines from public repositories. Triggers on phrases like "import
  from GitHub", "migrate contracts", "pull repo", "GitHub to REFINET", "import
  .sol files", "parse GitHub contracts", "ABI from GitHub", "SDK from repo",
  "contract migration", "repo import", "GitHub URL", "clone contracts",
  "import protocol", "migrate DeFi contracts", "GitHub MCP", "git clone contracts",
  "repo migrator", "contract ingestion", "import from git", "GROOT migrate",
  "pull contracts from", "Bitcoin script import", "Solana program import",
  "Hedera contract import", "XRPL import", "Algorand TEAL import", "XLM import",
  or any request involving a GitHub URL and smart contract files. Also triggers
  when a user provides a github.com URL in conversation with GROOT and mentions
  contracts, migration, import, or ABI.
---

# REFINET Repo Migrator — Autonomous GitHub-to-REFINET Contract Migration

This skill gives Claude everything needed to:
1. Accept a GitHub repo URL from a user and pull all contract files via GitHub API or MCP
2. Detect contract language/ecosystem (Solidity, Vyper, Rust/Anchor, Move, Bitcoin Script, TEAL, Stellar)
3. Compile Solidity to ABI or parse existing ABI/IDL files for non-EVM chains
4. Classify functions as public vs owner-only based on access control modifiers
5. Generate separate Public SDK and Owner SDK for each contract
6. Import everything into the user's private GROOT Brain repo in proper registry format
7. Trigger the knowledge-curator to sync CAG index with the new contracts

---

## Part 1 — Migration Pipeline Architecture

### 1.1 End-to-End Flow

```
User provides GitHub URL to GROOT
    │
    ▼
STEP 1: FETCH — Pull repo contents via GitHub API / MCP
    ├── List repo tree (GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1)
    ├── Filter for contract files by extension
    └── Download raw file contents
    │
    ▼
STEP 2: DETECT — Identify contract ecosystem
    ├── .sol          → Solidity (EVM: Ethereum, Polygon, Arbitrum, Optimism, Base)
    ├── .vy           → Vyper (EVM)
    ├── .rs + Anchor  → Rust/Anchor (Solana)
    ├── .move         → Move (Sui, Aptos)
    ├── .clar         → Clarity (Stacks/Bitcoin)
    ├── .teal / .py   → TEAL/PyTEAL (Algorand)
    ├── .js + xrpl    → XRPL Hooks (XRP Ledger)
    ├── .sol + hedera  → Solidity on Hedera (HTS)
    ├── .rs + stellar  → Soroban (Stellar/XLM)
    └── .json (ABI)   → Pre-compiled ABI (any EVM chain)
    │
    ▼
STEP 3: COMPILE / PARSE — Extract ABI or interface definition
    ├── Solidity:  solc-js compile → ABI JSON
    ├── Vyper:     vyper compile → ABI JSON
    ├── Anchor:    Parse IDL from anchor build artifacts or IDL JSON
    ├── Move:      Parse module interface from source
    ├── TEAL:      Parse ABI from ARC-4 annotations or PyTEAL hints
    ├── XRPL:      Extract hook parameters and invoke patterns
    ├── Hedera:    solc compile (Solidity-compatible) + HTS token patterns
    ├── Soroban:   Parse contract spec from .rs or .json
    └── Raw ABI:   Validate and normalize JSON structure
    │
    ▼
STEP 4: CLASSIFY — Separate public vs owner-only functions
    ├── EVM:     onlyOwner, onlyRole, require(msg.sender==owner), AccessControl
    ├── Anchor:  #[access_control], has_one, constraint checks
    ├── Move:    signer checks, friend visibility
    ├── Others:  Pattern-match on auth/permission checks per ecosystem
    │
    ▼
STEP 5: SDK GENERATION — Create Public SDK + Owner SDK
    ├── Public SDK:   Functions callable by any address
    ├── Owner SDK:    Functions restricted to owner/admin/role
    ├── Each SDK:     Function name, params, return types, description, usage example
    │
    ▼
STEP 6: IMPORT — Store in user's GROOT Brain private repo
    ├── POST /repo/contracts           — Create contract entry
    ├── POST /registry/projects        — Create registry project
    ├── POST /registry/projects/{id}/abis — Upload ABI
    ├── Store source files (never exposed in agent context per SAFETY.md)
    ├── Flag dangerous functions (delegatecall, selfdestruct, etc.)
    │
    ▼
STEP 7: INDEX — Trigger knowledge-curator for CAG sync
    └── New ABIs → CAG index → GROOT can answer questions about these contracts
```

### 1.2 Supported Ecosystems

| Ecosystem | Extensions | Compiler/Parser | ABI Format | Chain IDs |
|---|---|---|---|---|
| Solidity (EVM) | `.sol` | `solc-js` (npm, free) | EVM ABI JSON | 1,137,42161,10,8453 |
| Vyper (EVM) | `.vy` | `vyper` (pip, free) | EVM ABI JSON | 1,137,42161,10,8453 |
| Anchor (Solana) | `.rs` + `Anchor.toml` | IDL parse (no compile needed) | Anchor IDL JSON | solana-mainnet |
| Move (Sui/Aptos) | `.move` | AST parse | Move module interface | sui-mainnet, aptos-mainnet |
| Clarity (Bitcoin/Stacks) | `.clar` | Clarity parser | Clarity ABI | stacks-mainnet |
| TEAL (Algorand) | `.teal`, `.py` (PyTEAL) | ARC-4 parse | Algorand ABI JSON | algorand-mainnet |
| XRPL Hooks | `.c`, `.js` | Hook param parse | XRPL Hook spec | xrpl-mainnet |
| Hedera (HTS) | `.sol` | `solc-js` + HTS detection | EVM ABI JSON + HTS | hedera-mainnet |
| Soroban (Stellar/XLM) | `.rs` + `Cargo.toml` | Contract spec parse | Soroban spec JSON | stellar-mainnet |

### 1.3 GitHub Access Methods

Priority order (all free, no API keys required for public repos):

1. **GitHub MCP Server** — If user has GitHub MCP connected, use `mcp.github.*` tools
2. **GitHub REST API** — `api.github.com` (60 req/hour unauthenticated, 5000 with token)
3. **Raw content fetch** — `raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}`

```python
# Parse GitHub URL into components
import re

def parse_github_url(url: str) -> dict:
    """Extract owner, repo, branch, and optional path from any GitHub URL format."""
    patterns = [
        # https://github.com/owner/repo
        r"github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
        # https://github.com/owner/repo/tree/branch
        r"github\.com/([^/]+)/([^/]+)/tree/([^/]+)(?:/(.*))?",
        # https://github.com/owner/repo/blob/branch/path
        r"github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.*)",
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            groups = m.groups()
            return {
                "owner": groups[0],
                "repo": groups[1],
                "branch": groups[2] if len(groups) > 2 else "main",
                "path": groups[3] if len(groups) > 3 and groups[3] else None
            }
    return None
```

---

## Part 2 — Contract File Detection

### 2.1 File Extension Map

```python
CONTRACT_EXTENSIONS = {
    # EVM
    ".sol": {"ecosystem": "solidity", "chains": ["ethereum", "polygon", "arbitrum", "optimism", "base", "hedera"]},
    ".vy": {"ecosystem": "vyper", "chains": ["ethereum", "polygon", "arbitrum", "optimism", "base"]},

    # Solana
    ".rs": {"ecosystem": "rust", "chains": ["solana", "stellar"]},  # disambiguate via Anchor.toml or Cargo.toml

    # Move
    ".move": {"ecosystem": "move", "chains": ["sui", "aptos"]},

    # Bitcoin / Stacks
    ".clar": {"ecosystem": "clarity", "chains": ["stacks", "bitcoin"]},

    # Algorand
    ".teal": {"ecosystem": "teal", "chains": ["algorand"]},

    # Pre-compiled
    ".json": {"ecosystem": "abi_json", "chains": ["any"]},  # check if valid ABI structure
    ".abi": {"ecosystem": "abi_json", "chains": ["any"]},
}

# Context files that help disambiguate
CONTEXT_FILES = {
    "Anchor.toml": "solana_anchor",
    "Move.toml": "move",
    "Cargo.toml": "rust_generic",  # could be Solana, Stellar, or other
    "soroban": "stellar_soroban",  # check in Cargo.toml dependencies
    "hardhat.config": "evm_hardhat",
    "foundry.toml": "evm_foundry",
    "truffle-config": "evm_truffle",
    "brownie-config": "evm_brownie",
}
```

### 2.2 Disambiguation Logic

When `.rs` files are found, check context:
- `Anchor.toml` present → Solana Anchor program
- `Cargo.toml` contains `soroban-sdk` → Stellar Soroban contract
- `Cargo.toml` contains `ink` → ink! (Polkadot/Substrate) contract
- Otherwise → generic Rust (flag for manual review)

When `.py` files are found alongside `.teal`:
- Contains `pyteal` import → Algorand PyTEAL
- Contains `beaker` import → Algorand Beaker framework

---

## Part 3 — ABI Extraction by Ecosystem

### 3.1 Solidity (solc-js) — Zero Cost, CPU Only

```python
import subprocess
import json
import tempfile
import os

def compile_solidity(source_code: str, filename: str = "Contract.sol") -> dict:
    """Compile Solidity source to ABI using solc-js (npm package, free)."""
    # Write source to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sol', delete=False) as f:
        f.write(source_code)
        temp_path = f.name

    try:
        # Use solc standard JSON input
        input_json = json.dumps({
            "language": "Solidity",
            "sources": {filename: {"content": source_code}},
            "settings": {
                "outputSelection": {"*": {"*": ["abi", "evm.bytecode.object"]}}
            }
        })

        result = subprocess.run(
            ["npx", "solcjs", "--standard-json"],
            input=input_json, capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            # Try with solc binary if available
            result = subprocess.run(
                ["solc", "--standard-json"],
                input=input_json, capture_output=True, text=True, timeout=60
            )

        output = json.loads(result.stdout)
        contracts = {}

        for source_name, source_contracts in output.get("contracts", {}).items():
            for contract_name, contract_data in source_contracts.items():
                contracts[contract_name] = {
                    "abi": contract_data.get("abi", []),
                    "bytecode": contract_data.get("evm", {}).get("bytecode", {}).get("object", ""),
                    "source_file": source_name
                }

        errors = [e for e in output.get("errors", []) if e.get("severity") == "error"]
        return {"contracts": contracts, "errors": errors, "success": len(errors) == 0}

    finally:
        os.unlink(temp_path)
```

### 3.2 Anchor IDL (Solana) — Parse, No Compile

```python
def parse_anchor_idl(idl_json: dict) -> dict:
    """Convert Anchor IDL to a normalized ABI-like structure."""
    functions = []
    for instruction in idl_json.get("instructions", []):
        fn = {
            "name": instruction["name"],
            "type": "function",
            "inputs": [
                {"name": arg["name"], "type": str(arg["type"])}
                for arg in instruction.get("args", [])
            ],
            "accounts": [
                {"name": acc["name"], "isMut": acc.get("isMut", False), "isSigner": acc.get("isSigner", False)}
                for acc in instruction.get("accounts", [])
            ],
            "is_owner_only": any(
                acc.get("isSigner", False) and acc.get("name") in ("authority", "owner", "admin", "payer")
                for acc in instruction.get("accounts", [])
            )
        }
        functions.append(fn)

    return {
        "name": idl_json.get("name", "unknown"),
        "version": idl_json.get("version", "0.0.0"),
        "functions": functions,
        "accounts": idl_json.get("accounts", []),
        "types": idl_json.get("types", []),
        "events": idl_json.get("events", []),
        "errors": idl_json.get("errors", [])
    }
```

### 3.3 Non-EVM Fallback — LLM-Assisted Parsing

For ecosystems without a local compiler (Move, TEAL, XRPL Hooks, Soroban), use the LLM fallback chain to analyze source code:

```python
def llm_parse_contract(source_code: str, ecosystem: str, filename: str) -> dict:
    """Use the zero-cost LLM fallback chain to parse non-EVM contracts."""
    prompt = f"""Analyze this {ecosystem} smart contract source file ({filename}).
Extract the interface in this exact JSON format:
{{
  "name": "ContractName",
  "functions": [
    {{
      "name": "function_name",
      "type": "function",
      "inputs": [{{"name": "param", "type": "type"}}],
      "outputs": [{{"name": "", "type": "type"}}],
      "is_owner_only": true/false,
      "description": "What this function does"
    }}
  ],
  "events": [...],
  "errors": [...]
}}

Mark is_owner_only=true for functions that require admin/authority/owner signatures.

Source code:
```
{source_code[:8000]}
```

Respond with ONLY the JSON, no other text."""

    # This runs through run_agent.sh fallback chain:
    # Claude Code CLI → Ollama → BitNet → Gemini Flash
    return prompt  # Caller executes via the agent pipeline
```

---

## Part 4 — Access Control Classification

### 4.1 EVM Access Patterns

```python
OWNER_PATTERNS = {
    "modifiers": [
        r"onlyOwner", r"onlyAdmin", r"onlyRole", r"onlyMinter",
        r"onlyPauser", r"onlyGovernance", r"whenNotPaused",
        r"onlyAuthorized", r"onlyOperator", r"restricted"
    ],
    "require_patterns": [
        r"require\s*\(\s*msg\.sender\s*==\s*owner",
        r"require\s*\(\s*msg\.sender\s*==\s*admin",
        r"require\s*\(\s*hasRole\s*\(",
        r"require\s*\(\s*_msgSender\(\)\s*==\s*owner",
        r"_checkOwner\(\)",
        r"_checkRole\(",
    ],
    "openzeppelin": [
        r"Ownable", r"AccessControl", r"AccessControlEnumerable",
        r"Pausable", r"TimelockController"
    ]
}

def classify_evm_function(function_abi: dict, source_code: str, function_name: str) -> str:
    """Classify an EVM function as 'public' or 'owner_only'."""
    import re
    # Find the function definition in source
    fn_pattern = rf"function\s+{re.escape(function_name)}\s*\([^)]*\)[^{{]*\{{"
    match = re.search(fn_pattern, source_code, re.DOTALL)
    if not match:
        return "public"  # Default if can't find source

    # Get the function signature line (between 'function' and '{')
    fn_header = source_code[match.start():match.end()]

    # Check for owner modifiers in the header
    for pattern in OWNER_PATTERNS["modifiers"]:
        if re.search(pattern, fn_header):
            return "owner_only"

    # Check first 5 lines of function body for require patterns
    brace_pos = match.end()
    fn_body_start = source_code[brace_pos:brace_pos + 500]
    for pattern in OWNER_PATTERNS["require_patterns"]:
        if re.search(pattern, fn_body_start):
            return "owner_only"

    # View-only functions are always public
    if function_abi.get("stateMutability") in ("view", "pure"):
        return "public"

    return "public"
```

---

## Part 5 — SDK Generation

### 5.1 SDK Structure

Each contract gets two SDK documents:

```
ContractName/
├── public_sdk.md      — Functions callable by anyone
├── owner_sdk.md       — Functions requiring owner/admin access
└── full_abi.json      — Complete ABI for reference
```

### 5.2 SDK Entry Format

```markdown
### transfer(address to, uint256 amount) → bool

**Access**: Public
**State**: nonpayable
**Description**: Transfer tokens from caller to recipient.

**Parameters**:
- `to` (address): Recipient wallet address
- `amount` (uint256): Number of tokens (in smallest unit, e.g. wei)

**Returns**: `bool` — true if transfer succeeded

**Example** (ethers.js):
```javascript
const tx = await contract.transfer("0xRecipient...", ethers.parseUnits("100", 18));
await tx.wait();
```
```

### 5.3 Generation Function

```python
def generate_sdk_entry(function_abi: dict, access: str, ecosystem: str) -> str:
    """Generate an SDK markdown entry for a single function."""
    name = function_abi.get("name", "unknown")
    inputs = function_abi.get("inputs", [])
    outputs = function_abi.get("outputs", [])
    mutability = function_abi.get("stateMutability", "nonpayable")

    # Build signature
    param_str = ", ".join(f"{p.get('type','')} {p.get('name','')}" for p in inputs)
    return_str = ", ".join(p.get("type", "") for p in outputs)
    sig = f"{name}({param_str})"
    if return_str:
        sig += f" → {return_str}"

    # Build parameter docs
    param_docs = ""
    for p in inputs:
        param_docs += f"- `{p.get('name', '')}` ({p.get('type', '')})\n"

    return f"""### {sig}

**Access**: {access.replace('_', ' ').title()}
**State**: {mutability}

**Parameters**:
{param_docs if param_docs else '- None'}
"""
```

---

## Part 6 — Import into GROOT Brain

### 6.1 Registry Import Flow

```python
def import_to_registry(user_id: str, repo_info: dict, contracts: list[dict]) -> dict:
    """Import parsed contracts into the user's GROOT Brain private repo."""
    results = {"imported": 0, "errors": [], "project_ids": []}

    for contract in contracts:
        # 1. Create registry project
        project = {
            "name": contract["name"],
            "category": detect_category(contract),
            "description": f"Imported from {repo_info['owner']}/{repo_info['repo']}",
            "visibility": "private",  # User's private repo
            "source_repo": f"https://github.com/{repo_info['owner']}/{repo_info['repo']}",
            "ecosystem": contract["ecosystem"]
        }
        # POST /repo/contracts → creates in user's @username namespace

        # 2. Upload ABI
        # POST /registry/projects/{id}/abis with full ABI JSON

        # 3. Store SDKs
        # public_sdk.md and owner_sdk.md stored as project attachments

        # 4. Flag dangerous functions (triggers contract-watcher)
        # Automatic via the existing ABI security scan pipeline

        results["imported"] += 1

    return results
```

### 6.2 Category Detection

```python
def detect_category(contract: dict) -> str:
    """Detect contract category from function signatures."""
    fn_names = {fn.get("name", "").lower() for fn in contract.get("abi", [])}

    if fn_names & {"transfer", "balanceof", "approve", "totalsupply", "allowance"}:
        return "Token"  # ERC-20
    if fn_names & {"safetransferfrom", "tokenuri", "ownerof"}:
        return "NFT"  # ERC-721
    if fn_names & {"swap", "addliquidity", "removeliquidity"}:
        return "DeFi"
    if fn_names & {"propose", "castVote", "execute", "queue"}:
        return "Governance"
    if fn_names & {"deposit", "withdraw", "bridge", "relay"}:
        return "Bridge"
    if fn_names & {"getlatestprice", "getprice", "latestanswer"}:
        return "Oracle"

    return "Utility"
```

---

## Part 7 — Cron Schedule

```yaml
# configs/repo-migrator-cron.yaml
schedules:
  # No scheduled tasks — this is a user-triggered workflow.
  # The agent activates when a user provides a GitHub URL to GROOT.
  #
  # However, we do run periodic maintenance:

  # Daily at 07:00 UTC — retry failed migrations
  - name: retry-failed
    cron: "0 7 * * *"
    agent: repo-migrator
    task: >
      Check migration_jobs table for jobs with status 'failed' or 'partial'.
      Retry compilation/parsing for any that failed due to transient errors
      (network timeout, compiler busy). Email admin summary of retries.

  # Weekly — migration stats digest
  - name: weekly-stats
    cron: "0 7 * * 1"
    agent: repo-migrator
    task: >
      Compile weekly migration stats: repos imported, contracts parsed,
      ABIs generated, SDKs created, ecosystems represented, failure rate.
      Email admin digest.
```

---

## Part 8 — Operating Procedures

### 8.1 When User Provides a GitHub URL

1. Parse URL with `parse_github_url()` → extract owner, repo, branch
2. Fetch repo tree via GitHub API or MCP
3. Filter for contract files using `CONTRACT_EXTENSIONS`
4. Detect ecosystem using extensions + context files
5. For each contract file:
   a. Download raw content
   b. Compile/parse to ABI (ecosystem-specific)
   c. Classify functions as public vs owner-only
   d. Generate Public SDK + Owner SDK
   e. Import into user's GROOT Brain
6. Trigger CAG index sync (delegate to knowledge-curator)
7. Run ABI security scan (delegate to contract-watcher)
8. Report to user: contracts imported, functions found, warnings

### 8.2 When Compilation Fails

1. Log the error with full context
2. Try alternate compiler version if Solidity (load remote version)
3. If still fails, use LLM-assisted parsing as fallback
4. If LLM parse also fails, store source file with status 'manual_review'
5. Email admin with failure details

---

## Part 9 — Safety Constraints

- Source code is stored but NEVER exposed in agent context per SAFETY.md
- Only ABIs and generated SDKs are used for CAG context injection
- Private repos require GitHub authentication (user provides token)
- All imported contracts go to the user's PRIVATE namespace by default
- Dangerous function flags are applied automatically at import time
- The agent never executes or deploys contracts — import and parse only
- GitHub API rate limits respected (60/hour unauth, backoff on 429)

---

## Part 10 — Reference Files

- `references/github-api.md` — GitHub REST API endpoints for repo content access
- `references/multi-chain-parsers.md` — Ecosystem-specific parsing strategies and tools

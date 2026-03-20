#!/usr/bin/env python3
"""
REFINET Repo Migrator — GitHub-to-REFINET Contract Migration
Fetches contract files from a public GitHub repo, parses ABIs,
classifies functions, generates SDKs, and imports into GROOT Brain.

Usage:
    python repo_migrate.py <github_url>                         # Migrate all contracts
    python repo_migrate.py <github_url> --dry-run               # Scan only, don't import
    python repo_migrate.py <github_url> --ecosystem solidity    # Filter by ecosystem
    python repo_migrate.py <github_url> --email                 # Email admin report
    python repo_migrate.py <github_url> --user-id user_123      # Set owning user
    python repo_migrate.py --retry                              # Retry failed migrations
    python repo_migrate.py --stats                              # Weekly stats digest

Environment:
    GITHUB_TOKEN         — Optional: increases rate limit from 60 to 5000/hour
    REFINET_API_BASE     — REFINET Cloud API base URL
    ADMIN_EMAIL          — Admin email for migration reports
    DATABASE_PATH        — Path to public.db (for retry/stats)
"""

import json
import os
import re
import sys
import subprocess
import smtplib
import tempfile
import time
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Optional

try:
    import httpx
except ImportError:
    os.system(f"{sys.executable} -m pip install httpx -q")
    import httpx

API_BASE = os.getenv("REFINET_API_BASE", "http://localhost:8000")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
MIGRATION_LOG = os.getenv("MIGRATION_LOG", "data/migration_jobs.json")

# ─────────────────────────────────────────────────────────────────
# URL Parsing
# ─────────────────────────────────────────────────────────────────
def parse_github_url(url: str) -> Optional[dict]:
    """Extract owner, repo, branch, and optional path from any GitHub URL."""
    patterns = [
        r"github\.com/([^/]+)/([^/]+)/tree/([^/]+)(?:/(.*))?",
        r"github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.*)",
        r"github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            g = m.groups()
            if len(g) == 2:
                return {"owner": g[0], "repo": g[1], "branch": "main", "path": None}
            return {
                "owner": g[0], "repo": g[1],
                "branch": g[2] if g[2] else "main",
                "path": g[3] if len(g) > 3 else None,
            }
    return None


# ─────────────────────────────────────────────────────────────────
# GitHub Fetching with Rate Limit Handling
# ─────────────────────────────────────────────────────────────────
CONTRACT_EXTENSIONS = {
    ".sol": "solidity", ".vy": "vyper", ".move": "move", ".clar": "clarity",
    ".teal": "teal", ".abi": "abi_json", ".rs": "rust",
}
EXCLUDE_DIRS = {
    "node_modules", "lib", ".git", "test", "tests", "mock", "mocks",
    "script", "scripts", "migrations", ".github", "deps", "build",
}

_rate_limit_remaining = 60
_rate_limit_reset = 0


def github_headers() -> dict:
    h = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"token {GITHUB_TOKEN}"
    return h


def github_get(url: str, params: Optional[dict] = None, timeout: int = 30) -> httpx.Response:
    """HTTP GET with rate limit awareness and backoff."""
    global _rate_limit_remaining, _rate_limit_reset

    # If we know we're rate-limited, wait
    if _rate_limit_remaining <= 1:
        wait = max(0, _rate_limit_reset - time.time()) + 1
        if wait > 0 and wait < 300:
            print(f"  [rate-limit] Waiting {wait:.0f}s for GitHub API reset...")
            time.sleep(wait)

    r = httpx.get(url, params=params, headers=github_headers(), timeout=timeout)

    # Track rate limit headers
    _rate_limit_remaining = int(r.headers.get("x-ratelimit-remaining", "60"))
    _rate_limit_reset = int(r.headers.get("x-ratelimit-reset", "0"))

    # Handle 429 with retry
    if r.status_code == 429:
        retry_after = int(r.headers.get("retry-after", "60"))
        print(f"  [rate-limit] 429 received, backing off {retry_after}s...")
        time.sleep(min(retry_after, 120))
        return github_get(url, params=params, timeout=timeout)

    return r


def fetch_repo_tree(owner: str, repo: str, branch: str) -> list:
    """Fetch full repo tree, trying multiple branch names."""
    for b in [branch, "main", "master"]:
        r = github_get(
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/{b}",
            params={"recursive": "1"},
        )
        if r.status_code == 200:
            return [
                {"path": item["path"], "size": item.get("size", 0)}
                for item in r.json().get("tree", [])
                if item["type"] == "blob"
            ]
    return []


def filter_contract_files(tree: list) -> list:
    """Filter repo tree for contract files, excluding test/lib/build dirs."""
    results = []
    for item in tree:
        path = item["path"]
        if any(ex in path.split("/") for ex in EXCLUDE_DIRS):
            continue
        ext = Path(path).suffix.lower()
        if ext in CONTRACT_EXTENSIONS:
            item["ecosystem"] = CONTRACT_EXTENSIONS[ext]
            results.append(item)
        elif ext == ".json" and any(d in path for d in ["artifacts", "out", "build", "idl"]):
            item["ecosystem"] = "abi_json"
            results.append(item)
        elif ext == ".py":
            # Check if this is PyTEAL (Algorand)
            basename = Path(path).stem.lower()
            if any(k in path.lower() for k in ["pyteal", "teal", "algorand", "arc4"]):
                item["ecosystem"] = "teal"
                results.append(item)
    return results


def fetch_file(owner: str, repo: str, branch: str, path: str) -> str:
    """Fetch raw file content from GitHub."""
    r = httpx.get(
        f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}",
        timeout=30, follow_redirects=True,
    )
    return r.text if r.status_code == 200 else ""


def detect_context(tree: list, owner: str, repo: str, branch: str) -> dict:
    """Detect project type from context files (Anchor.toml, Move.toml, Cargo.toml, etc.)."""
    paths = {item["path"] for item in tree}
    ctx = {"type": "unknown", "framework": None}

    if any("Anchor.toml" in p for p in paths):
        ctx = {"type": "solana_anchor", "framework": "Anchor"}
    elif any("Move.toml" in p for p in paths):
        ctx = {"type": "move", "framework": "Move"}
    elif any("hardhat.config" in p for p in paths):
        ctx = {"type": "evm", "framework": "Hardhat"}
    elif any("foundry.toml" in p for p in paths):
        ctx = {"type": "evm", "framework": "Foundry"}
    elif any("Clarinet.toml" in p for p in paths):
        ctx = {"type": "clarity", "framework": "Clarinet"}
    elif any("Cargo.toml" in p for p in paths):
        # Read root Cargo.toml to disambiguate Soroban vs generic Rust
        cargo_paths = [p for p in paths if p.endswith("Cargo.toml")]
        for cp in cargo_paths[:3]:
            content = fetch_file(owner, repo, branch, cp)
            if "soroban" in content.lower():
                ctx = {"type": "stellar_soroban", "framework": "Soroban"}
                break
            elif "anchor-lang" in content.lower():
                ctx = {"type": "solana_anchor", "framework": "Anchor"}
                break
            elif "ink" in content.lower() and "ink_lang" in content.lower():
                ctx = {"type": "ink_substrate", "framework": "ink!"}
                break
        if ctx["type"] == "unknown":
            ctx = {"type": "rust_generic", "framework": "Cargo"}

    return ctx


# ─────────────────────────────────────────────────────────────────
# Solidity Compilation (solc-js / solc, free, WASM on ARM)
# ─────────────────────────────────────────────────────────────────
def compile_solidity(source: str, filename: str) -> dict:
    """Compile Solidity to ABI using solc standard JSON input."""
    input_json = json.dumps({
        "language": "Solidity",
        "sources": {filename: {"content": source}},
        "settings": {"outputSelection": {"*": {"*": ["abi"]}}}
    })

    for cmd in [["solc", "--standard-json"], ["npx", "solcjs", "--standard-json"]]:
        try:
            result = subprocess.run(
                cmd, input=input_json, capture_output=True, text=True, timeout=60
            )
            if result.stdout.strip():
                output = json.loads(result.stdout)
                contracts = {}
                for src_name, src_contracts in output.get("contracts", {}).items():
                    for name, data in src_contracts.items():
                        abi = data.get("abi", [])
                        if abi:
                            contracts[name] = {"abi": abi, "source": src_name}
                errors = [
                    e["formattedMessage"]
                    for e in output.get("errors", [])
                    if e.get("severity") == "error"
                ]
                if contracts:
                    return {"success": True, "contracts": contracts, "errors": errors}
                elif errors:
                    return {"success": False, "contracts": {}, "errors": errors}
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as exc:
            continue

    return {"success": False, "contracts": {}, "errors": ["solc/solcjs not available — install with: npm install -g solc"]}


# ─────────────────────────────────────────────────────────────────
# Vyper Compilation
# ─────────────────────────────────────────────────────────────────
def compile_vyper(source: str, filename: str) -> dict:
    """Compile Vyper to ABI using the vyper compiler."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".vy", delete=False) as f:
        f.write(source)
        temp_path = f.name
    try:
        result = subprocess.run(
            ["vyper", "-f", "abi", temp_path],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0 and result.stdout.strip():
            abi = json.loads(result.stdout)
            name = Path(filename).stem
            return {"success": True, "contracts": {name: {"abi": abi}}, "errors": []}
        return {"success": False, "contracts": {}, "errors": [result.stderr[:500] if result.stderr else "vyper compilation failed"]}
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        return {"success": False, "contracts": {}, "errors": [f"vyper not available ({exc})"]}
    finally:
        os.unlink(temp_path)


# ─────────────────────────────────────────────────────────────────
# Anchor IDL Parsing (Solana — parse, no compile needed)
# ─────────────────────────────────────────────────────────────────
def parse_anchor_idl(content: str, filename: str) -> dict:
    """Parse Anchor IDL JSON into a normalized ABI structure."""
    try:
        idl = json.loads(content)
    except json.JSONDecodeError:
        return {"success": False, "contracts": {}, "errors": ["Not valid Anchor IDL JSON"]}

    if "instructions" not in idl:
        return {"success": False, "contracts": {}, "errors": ["No instructions field — not an Anchor IDL"]}

    functions = []
    for ix in idl.get("instructions", []):
        is_owner = any(
            acc.get("isSigner", False) and acc.get("name", "").lower() in ("authority", "owner", "admin", "payer", "signer")
            for acc in ix.get("accounts", [])
        )
        fn = {
            "name": ix["name"],
            "type": "function",
            "inputs": [{"name": a["name"], "type": str(a.get("type", "unknown"))} for a in ix.get("args", [])],
            "outputs": [],
            "stateMutability": "nonpayable",
            "_is_owner_only": is_owner,
            "_accounts": [
                {"name": a["name"], "isMut": a.get("isMut", False), "isSigner": a.get("isSigner", False)}
                for a in ix.get("accounts", [])
            ],
        }
        functions.append(fn)

    name = idl.get("name", Path(filename).stem)
    return {"success": True, "contracts": {name: {"abi": functions}}, "errors": []}


def parse_anchor_rs(source: str, filename: str) -> dict:
    """Extract basic interface info from Anchor Rust source (best-effort)."""
    functions = []
    # Match #[instruction] or pub fn patterns in Anchor programs
    for m in re.finditer(r"pub\s+fn\s+(\w+)\s*\(([^)]*)\)", source):
        fn_name = m.group(1)
        if fn_name.startswith("_"):
            continue
        params_str = m.group(2)
        inputs = []
        for param in params_str.split(","):
            param = param.strip()
            if ":" in param and "ctx" not in param.lower() and "Context" not in param:
                parts = param.split(":")
                inputs.append({"name": parts[0].strip(), "type": parts[1].strip() if len(parts) > 1 else "unknown"})

        is_owner = bool(re.search(
            r"(has_one\s*=\s*(authority|owner|admin)|#\[access_control|constraint\s*=.*authority)",
            source[max(0, m.start() - 200):m.start()],
        ))
        functions.append({
            "name": fn_name, "type": "function", "inputs": inputs, "outputs": [],
            "stateMutability": "nonpayable", "_is_owner_only": is_owner,
        })

    if not functions:
        return {"success": False, "contracts": {}, "errors": ["No public functions found in Anchor source"]}

    name = Path(filename).stem
    return {"success": True, "contracts": {name: {"abi": functions}}, "errors": []}


# ─────────────────────────────────────────────────────────────────
# Non-EVM LLM-Assisted Parsing (Move, Clarity, TEAL, XRPL, Soroban)
# ─────────────────────────────────────────────────────────────────
def llm_parse_contract(source: str, ecosystem: str, filename: str) -> dict:
    """
    Use the zero-cost LLM fallback chain to parse non-EVM contracts.
    Calls run_agent.sh which tries: Claude Code CLI -> Ollama -> BitNet -> Gemini Flash.
    Falls back to regex-based extraction if LLM is unavailable.
    """
    # First try regex-based extraction per ecosystem
    functions = regex_extract_interface(source, ecosystem, filename)
    if functions:
        name = Path(filename).stem
        return {"success": True, "contracts": {name: {"abi": functions}}, "errors": []}

    # Try LLM fallback via run_agent.sh
    agent_script = Path(__file__).parent.parent.parent / "refinet-platform-ops" / "scripts" / "run_agent.sh"
    if not agent_script.exists():
        agent_script = Path(__file__).resolve().parent.parent.parent / "refinet-platform-ops" / "scripts" / "run_agent.sh"

    if agent_script.exists():
        prompt = f"""Analyze this {ecosystem} smart contract ({filename}). Extract the interface as JSON:
{{"name":"ContractName","functions":[{{"name":"fn","type":"function","inputs":[{{"name":"p","type":"t"}}],"outputs":[],"stateMutability":"nonpayable","_is_owner_only":false}}]}}
Mark _is_owner_only=true for admin/authority functions.
Source (first 6000 chars):
{source[:6000]}
Respond with ONLY valid JSON."""

        try:
            result = subprocess.run(
                [str(agent_script), "repo-migrator", prompt],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0 and result.stdout.strip():
                # Try to extract JSON from output
                output = result.stdout.strip()
                json_match = re.search(r"\{.*\}", output, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    if "functions" in parsed:
                        name = parsed.get("name", Path(filename).stem)
                        return {"success": True, "contracts": {name: {"abi": parsed["functions"]}}, "errors": []}
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            pass

    return {"success": False, "contracts": {}, "errors": [f"{ecosystem} — LLM fallback unavailable, stored for manual review"]}


def regex_extract_interface(source: str, ecosystem: str, filename: str) -> list:
    """Best-effort regex extraction for non-EVM ecosystems."""
    functions = []

    if ecosystem == "move":
        # Move: public entry fun name(param: Type, ...)
        for m in re.finditer(r"public\s+(?:entry\s+)?fun\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)", source):
            fn_name = m.group(1)
            params = []
            for p in m.group(2).split(","):
                p = p.strip()
                if ":" in p and "&signer" not in p.lower():
                    parts = p.split(":")
                    params.append({"name": parts[0].strip(), "type": parts[1].strip()})
            is_owner = "&signer" in m.group(2).lower() or "signer" in m.group(2).lower()
            functions.append({
                "name": fn_name, "type": "function", "inputs": params,
                "outputs": [], "stateMutability": "nonpayable", "_is_owner_only": is_owner,
            })

    elif ecosystem == "clarity":
        # Clarity: (define-public (name (param type) ...))
        for m in re.finditer(r"\(define-(?:public|read-only)\s+\((\w+)((?:\s+\(\w+\s+\w+\))*)\s*\)", source):
            fn_name = m.group(1)
            param_str = m.group(2)
            params = []
            for pm in re.finditer(r"\((\w+)\s+(\w+)\)", param_str):
                params.append({"name": pm.group(1), "type": pm.group(2)})
            is_read = "(define-read-only" in source[max(0, m.start() - 20):m.start() + 20]
            is_owner = bool(re.search(r"tx-sender\s+contract-owner", source[m.start():m.start() + 500]))
            functions.append({
                "name": fn_name, "type": "function", "inputs": params,
                "outputs": [], "stateMutability": "view" if is_read else "nonpayable",
                "_is_owner_only": is_owner,
            })

    elif ecosystem == "teal":
        # TEAL/PyTEAL ARC-4: look for method signatures
        for m in re.finditer(r"(?:@ABIReturnSubroutine|method)\s*[(\"](\w+)", source):
            functions.append({
                "name": m.group(1), "type": "function", "inputs": [],
                "outputs": [], "stateMutability": "nonpayable", "_is_owner_only": False,
            })
        # PyTEAL: look for @external or Subroutine patterns
        for m in re.finditer(r"def\s+(\w+)\s*\(([^)]*)\).*?(?:@external|@internal|Subroutine)", source, re.DOTALL):
            fn_name = m.group(1)
            if not any(f["name"] == fn_name for f in functions):
                functions.append({
                    "name": fn_name, "type": "function", "inputs": [],
                    "outputs": [], "stateMutability": "nonpayable", "_is_owner_only": False,
                })

    elif ecosystem == "rust":
        # Generic Rust contract (Soroban, ink!, etc.)
        for m in re.finditer(r"(?:#\[contractimpl\]|impl\s+\w+)\s*\{[^}]*pub\s+fn\s+(\w+)\s*\(([^)]*)\)", source, re.DOTALL):
            fn_name = m.group(1)
            if fn_name.startswith("_"):
                continue
            params = []
            for p in m.group(2).split(","):
                p = p.strip()
                if ":" in p and "self" not in p.lower() and "env" not in p.lower():
                    parts = p.split(":")
                    params.append({"name": parts[0].strip(), "type": parts[1].strip()})
            functions.append({
                "name": fn_name, "type": "function", "inputs": params,
                "outputs": [], "stateMutability": "nonpayable", "_is_owner_only": False,
            })
        # Also try simpler pub fn matching for Soroban
        if not functions:
            for m in re.finditer(r"pub\s+fn\s+(\w+)\s*\(([^)]*)\)", source):
                fn_name = m.group(1)
                if fn_name.startswith("_") or fn_name in ("new", "default"):
                    continue
                functions.append({
                    "name": fn_name, "type": "function", "inputs": [],
                    "outputs": [], "stateMutability": "nonpayable", "_is_owner_only": False,
                })

    return functions


# ─────────────────────────────────────────────────────────────────
# Pre-compiled ABI Parsing
# ─────────────────────────────────────────────────────────────────
def parse_abi_json(content: str) -> dict:
    """Parse a pre-compiled ABI JSON file (Hardhat artifact, raw ABI, or Anchor IDL)."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {"success": False, "contracts": {}, "errors": ["Invalid JSON"]}

    # Hardhat/Foundry artifact format: {"abi": [...], "contractName": "..."}
    if isinstance(data, dict) and "abi" in data:
        name = data.get("contractName", data.get("name", "Unknown"))
        return {"success": True, "contracts": {name: {"abi": data["abi"]}}, "errors": []}

    # Anchor IDL format: {"instructions": [...]}
    if isinstance(data, dict) and "instructions" in data:
        return parse_anchor_idl(content, "idl.json")

    # Raw ABI array
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        return {"success": True, "contracts": {"Contract": {"abi": data}}, "errors": []}

    return {"success": False, "contracts": {}, "errors": ["Unrecognized JSON format (not ABI, artifact, or IDL)"]}


# ─────────────────────────────────────────────────────────────────
# Access Control Classification
# ─────────────────────────────────────────────────────────────────
OWNER_MODIFIERS = re.compile(
    r"onlyOwner|onlyAdmin|onlyRole|onlyMinter|onlyOperator|onlyGovernance|"
    r"onlyPauser|onlyAuthorized|restricted|whenNotPaused",
    re.IGNORECASE,
)
OWNER_REQUIRES = re.compile(
    r"require\s*\(\s*msg\.sender\s*==\s*(owner|admin)|"
    r"require\s*\(\s*_msgSender\(\)\s*==\s*owner|"
    r"_checkOwner|_checkRole|hasRole\s*\(",
    re.IGNORECASE,
)

# Dangerous patterns that should be flagged
DANGEROUS_PATTERNS = [
    ("delegatecall", re.compile(r"\.delegatecall\s*\(", re.IGNORECASE)),
    ("selfdestruct", re.compile(r"selfdestruct\s*\(|SELFDESTRUCT", re.IGNORECASE)),
    ("tx.origin", re.compile(r"tx\.origin", re.IGNORECASE)),
    ("unchecked_call", re.compile(r"\.call\{.*\}\s*\([^)]*\)(?!\s*;?\s*require)", re.DOTALL)),
    ("infinite_approval", re.compile(r"type\(uint256\)\.max|2\*\*256\s*-\s*1|0xfff+", re.IGNORECASE)),
    ("inline_assembly", re.compile(r"assembly\s*\{", re.IGNORECASE)),
    ("proxy_pattern", re.compile(r"_implementation\(\)|upgradeTo\(|IMPLEMENTATION_SLOT", re.IGNORECASE)),
    ("ownership_transfer", re.compile(r"transferOwnership\s*\(|renounceOwnership\s*\(", re.IGNORECASE)),
]


def classify_function(fn: dict, source: str) -> str:
    """Classify a function as 'public' or 'owner_only'."""
    # If the parser already flagged it (Anchor, Move, Clarity, etc.)
    if fn.get("_is_owner_only"):
        return "owner_only"

    name = fn.get("name", "")
    if not name or fn.get("type") != "function":
        return "public"
    if fn.get("stateMutability") in ("view", "pure"):
        return "public"

    # EVM: search source for modifier/require patterns
    pattern = rf"function\s+{re.escape(name)}\s*\([^)]*\)[^{{]*\{{"
    match = re.search(pattern, source, re.DOTALL)
    if match:
        header = source[match.start():match.end()]
        body = source[match.end():match.end() + 500]
        if OWNER_MODIFIERS.search(header) or OWNER_REQUIRES.search(body):
            return "owner_only"

    return "public"


def detect_dangerous_patterns(source: str) -> list:
    """Detect dangerous patterns in source code for security flagging."""
    found = []
    for pattern_name, pattern_re in DANGEROUS_PATTERNS:
        if pattern_re.search(source):
            found.append(pattern_name)
    return found


# ─────────────────────────────────────────────────────────────────
# SDK Generation
# ─────────────────────────────────────────────────────────────────
def generate_sdk(contract_name: str, abi: list, source: str) -> dict:
    """Generate Public SDK and Owner SDK markdown documents."""
    public_entries = []
    owner_entries = []

    for fn in abi:
        if fn.get("type") != "function":
            continue
        access = classify_function(fn, source)
        name = fn.get("name", "")
        inputs = fn.get("inputs", [])
        outputs = fn.get("outputs", [])
        mutability = fn.get("stateMutability", "nonpayable")

        param_str = ", ".join(f"{p.get('type', '')} {p.get('name', '')}" for p in inputs)
        ret_str = ", ".join(p.get("type", "") for p in outputs)
        sig = f"{name}({param_str})"
        if ret_str:
            sig += f" -> {ret_str}"

        entry = f"### {sig}\n\n**Access**: {access.replace('_', ' ').title()}\n**State**: {mutability}\n\n"
        if inputs:
            entry += "**Parameters**:\n"
            for p in inputs:
                entry += f"- `{p.get('name', '')}` ({p.get('type', '')})\n"
            entry += "\n"

        if access == "owner_only":
            owner_entries.append(entry)
        else:
            public_entries.append(entry)

    public_sdk = ""
    if public_entries:
        public_sdk = f"# {contract_name} — Public SDK\n\nFunctions callable by any address.\n\n" + "\n".join(public_entries)

    owner_sdk = ""
    if owner_entries:
        owner_sdk = f"# {contract_name} — Owner SDK\n\nFunctions restricted to owner/admin/role holders.\n\n" + "\n".join(owner_entries)

    return {
        "public_sdk": public_sdk,
        "owner_sdk": owner_sdk,
        "public_count": len(public_entries),
        "owner_count": len(owner_entries),
    }


# ─────────────────────────────────────────────────────────────────
# Category Detection
# ─────────────────────────────────────────────────────────────────
def detect_category(abi: list) -> str:
    """Detect contract category from function names (case-insensitive)."""
    names = {fn.get("name", "").lower() for fn in abi if fn.get("type") == "function"}

    if names & {"transfer", "balanceof", "approve", "totalsupply", "allowance"}:
        return "Token"
    if names & {"safetransferfrom", "tokenuri", "ownerof"}:
        return "NFT"
    if names & {"swap", "addliquidity", "removeliquidity", "getamountsout"}:
        return "DeFi"
    if names & {"propose", "castvote", "execute", "queue", "castVote".lower()}:
        return "Governance"
    if names & {"deposit", "withdraw", "bridge", "relay"}:
        return "Bridge"
    if names & {"getlatestprice", "getprice", "latestanswer", "latestrounddata"}:
        return "Oracle"
    if names & {"stake", "unstake", "claimrewards", "getreward"}:
        return "Staking"

    return "Utility"


# ─────────────────────────────────────────────────────────────────
# GROOT Brain Import (API calls)
# ─────────────────────────────────────────────────────────────────
def import_to_groot_brain(
    user_id: str,
    repo_info: dict,
    contract_name: str,
    abi: list,
    sdk: dict,
    category: str,
    ecosystem: str,
    dangerous_patterns: list,
    source_path: str,
) -> dict:
    """Import a parsed contract into the user's GROOT Brain via REFINET API."""
    result = {"imported": False, "project_id": None, "errors": []}
    source_url = f"https://github.com/{repo_info['owner']}/{repo_info['repo']}"

    try:
        client = httpx.Client(base_url=API_BASE, timeout=30)

        # Step 1: Create contract in user's GROOT Brain repo
        contract_payload = {
            "name": contract_name,
            "description": f"Imported from {repo_info['owner']}/{repo_info['repo']}",
            "abi": abi,
            "category": category,
            "ecosystem": ecosystem,
            "source_repo": source_url,
            "source_path": source_path,
            "dangerous_patterns": dangerous_patterns,
        }
        r = client.post(
            f"/repo/contracts",
            json=contract_payload,
            params={"user_id": user_id},
        )
        if r.status_code not in (200, 201):
            result["errors"].append(f"POST /repo/contracts failed: {r.status_code} {r.text[:200]}")

        # Step 2: Create registry project
        project_payload = {
            "name": contract_name,
            "category": category,
            "description": f"Migrated from {source_url}",
            "visibility": "private",
        }
        r = client.post("/registry/projects", json=project_payload, params={"user_id": user_id})
        project_id = None
        if r.status_code in (200, 201):
            body = r.json()
            project_id = body.get("id") or body.get("project_id")
            result["project_id"] = project_id
        else:
            result["errors"].append(f"POST /registry/projects failed: {r.status_code}")

        # Step 3: Upload ABI to registry project
        if project_id:
            r = client.post(
                f"/registry/projects/{project_id}/abis",
                json={"abi": abi, "name": contract_name, "ecosystem": ecosystem},
            )
            if r.status_code not in (200, 201):
                result["errors"].append(f"ABI upload failed: {r.status_code}")

        # Step 4: Store SDK documents as project attachments
        if project_id and sdk.get("public_sdk"):
            client.post(
                f"/registry/projects/{project_id}/attachments",
                json={"name": "public_sdk.md", "content": sdk["public_sdk"]},
            )
        if project_id and sdk.get("owner_sdk"):
            client.post(
                f"/registry/projects/{project_id}/attachments",
                json={"name": "owner_sdk.md", "content": sdk["owner_sdk"]},
            )

        result["imported"] = True
        client.close()

    except httpx.ConnectError:
        result["errors"].append(f"Cannot reach REFINET API at {API_BASE} — is the server running?")
    except Exception as exc:
        result["errors"].append(f"Import error: {str(exc)[:200]}")

    return result


# ─────────────────────────────────────────────────────────────────
# Post-Import Delegation (CAG sync + security scan)
# ─────────────────────────────────────────────────────────────────
def delegate_cag_sync(contract_names: list):
    """Trigger knowledge-curator to sync CAG index with new contracts."""
    print("\n[migrator] Delegating CAG index sync to knowledge-curator...")
    try:
        r = httpx.post(
            f"{API_BASE}/agents/knowledge-curator/run",
            json={"task": f"Sync CAG index for newly imported contracts: {', '.join(contract_names)}"},
            timeout=15,
        )
        if r.status_code in (200, 201, 202):
            print("  -> CAG sync task queued")
        else:
            print(f"  -> CAG sync delegation returned {r.status_code} (API may be offline)")
    except httpx.ConnectError:
        print("  -> CAG sync skipped (API not reachable)")
    except Exception as e:
        print(f"  -> CAG sync failed: {e}")


def delegate_security_scan(contract_names: list):
    """Trigger contract-watcher to scan imported ABIs for dangerous patterns."""
    print("[migrator] Delegating ABI security scan to contract-watcher...")
    try:
        r = httpx.post(
            f"{API_BASE}/agents/contract-watcher/run",
            json={"task": f"Scan ABIs for dangerous patterns: {', '.join(contract_names)}"},
            timeout=15,
        )
        if r.status_code in (200, 201, 202):
            print("  -> Security scan task queued")
        else:
            print(f"  -> Security scan delegation returned {r.status_code} (API may be offline)")
    except httpx.ConnectError:
        print("  -> Security scan skipped (API not reachable)")
    except Exception as e:
        print(f"  -> Security scan failed: {e}")


# ─────────────────────────────────────────────────────────────────
# Migration Job Persistence (for retry and stats)
# ─────────────────────────────────────────────────────────────────
def load_migration_jobs() -> list:
    """Load migration jobs from JSON log."""
    path = Path(MIGRATION_LOG)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return []


def save_migration_job(job: dict):
    """Append a migration job to the JSON log."""
    path = Path(MIGRATION_LOG)
    path.parent.mkdir(parents=True, exist_ok=True)
    jobs = load_migration_jobs()
    # Update existing job if same repo+user combo
    updated = False
    for i, j in enumerate(jobs):
        if j.get("repo") == job.get("repo") and j.get("user_id") == job.get("user_id"):
            jobs[i] = job
            updated = True
            break
    if not updated:
        jobs.append(job)
    path.write_text(json.dumps(jobs, indent=2, default=str))


def retry_failed_migrations():
    """Retry failed/partial migrations from the job log."""
    jobs = load_migration_jobs()
    failed = [j for j in jobs if j.get("status") in ("failed", "partial")]
    if not failed:
        print("[migrator] No failed migrations to retry")
        return

    print(f"[migrator] Found {len(failed)} failed migration(s) to retry")
    retried = 0
    for job in failed:
        url = job.get("url", "")
        user_id = job.get("user_id", "admin")
        if url:
            print(f"  Retrying: {url}")
            # Re-run main migration for this URL
            old_argv = sys.argv
            sys.argv = ["repo_migrate.py", url, "--user-id", user_id, "--email"]
            try:
                main()
                retried += 1
            except SystemExit:
                pass
            finally:
                sys.argv = old_argv

    print(f"[migrator] Retried {retried}/{len(failed)} failed migrations")
    return {"retried": retried, "total_failed": len(failed)}


def weekly_stats_digest():
    """Compile and print weekly migration stats."""
    jobs = load_migration_jobs()
    now = datetime.now(timezone.utc)

    # Filter to last 7 days
    recent = []
    for j in jobs:
        ts = j.get("timestamp", "")
        if ts:
            try:
                job_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if (now - job_time).days <= 7:
                    recent.append(j)
            except (ValueError, TypeError):
                pass

    total_repos = len(recent)
    total_contracts = sum(j.get("imported", 0) for j in recent)
    total_failed = sum(1 for j in recent if j.get("status") == "failed")
    ecosystems = set()
    for j in recent:
        ecosystems.update(j.get("ecosystems", []))

    stats = {
        "period": "last_7_days",
        "repos_imported": total_repos,
        "contracts_parsed": total_contracts,
        "failures": total_failed,
        "failure_rate": f"{(total_failed / max(total_repos, 1) * 100):.1f}%",
        "ecosystems": sorted(ecosystems),
    }

    print(f"\n[migrator] Weekly Stats Digest")
    print(f"  Repos imported: {total_repos}")
    print(f"  Contracts parsed: {total_contracts}")
    print(f"  Failures: {total_failed}")
    print(f"  Failure rate: {stats['failure_rate']}")
    print(f"  Ecosystems: {', '.join(stats['ecosystems']) or 'none'}")

    # Email if configured
    admin = os.getenv("ADMIN_EMAIL")
    if admin:
        ts = now.strftime("%Y-%m-%d %H:%M UTC")
        html = f"""<div style="font-family:sans-serif;max-width:600px;margin:0 auto">
          <div style="background:#1a1a2e;color:#e0e0e0;padding:16px 20px;border-radius:8px 8px 0 0">
            <h2 style="margin:0;font-size:18px">Weekly Migration Stats — {ts}</h2></div>
          <div style="background:#16213e;color:#e0e0e0;padding:20px;border-radius:0 0 8px 8px">
            <p>Repos: {total_repos} | Contracts: {total_contracts} | Failed: {total_failed}</p>
            <p>Ecosystems: {', '.join(stats['ecosystems']) or 'none'}</p>
            <hr style="border:none;border-top:1px solid #333;margin:16px 0">
            <p style="font-size:11px;color:#666">GROOT Repo Migrator Agent — Weekly Digest</p></div></div>"""
        send_email(f"[REFINET REGISTRY] Weekly Migration Stats — {ts}", html, json.dumps(stats, indent=2))

    return stats


# ─────────────────────────────────────────────────────────────────
# Email Reporting
# ─────────────────────────────────────────────────────────────────
def send_email(subject: str, html: str, text: str):
    """Send admin email via self-hosted SMTP."""
    admin = os.getenv("ADMIN_EMAIL")
    if not admin:
        print("[migrator] ADMIN_EMAIL not set, skipping email")
        return
    msg = MIMEMultipart("alternative")
    msg["From"] = os.getenv("MAIL_FROM", "groot@refinet.io")
    msg["To"] = admin
    msg["Subject"] = subject
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP(os.getenv("SMTP_HOST", "127.0.0.1"), int(os.getenv("SMTP_PORT", "8025"))) as s:
            s.send_message(msg)
            print(f"[migrator] Email sent to {admin}")
    except Exception as e:
        print(f"[migrator] Email failed: {e} (SMTP at {os.getenv('SMTP_HOST', '127.0.0.1')}:{os.getenv('SMTP_PORT', '8025')})")


# ─────────────────────────────────────────────────────────────────
# Main Migration Flow
# ─────────────────────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="REFINET Repo Migrator — GitHub-to-REFINET Contract Migration",
        epilog="Examples:\n"
               "  python repo_migrate.py https://github.com/OpenZeppelin/openzeppelin-contracts\n"
               "  python repo_migrate.py https://github.com/Uniswap/v3-core --dry-run\n"
               "  python repo_migrate.py --retry --email\n"
               "  python repo_migrate.py --stats --email",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("url", nargs="?", default=None, help="GitHub repository URL to migrate")
    parser.add_argument("--retry", action="store_true", help="Retry failed migrations")
    parser.add_argument("--stats", action="store_true", help="Show weekly migration stats digest")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and scan without importing")
    parser.add_argument("--email", action="store_true", help="Send email report to admin")
    parser.add_argument("--ecosystem", type=str, default=None, help="Filter by ecosystem (e.g., solidity, anchor)")
    parser.add_argument("--user-id", type=str, default="admin", help="User ID for private repo import")
    args = parser.parse_args()

    # Handle maintenance commands
    if args.retry:
        retry_failed_migrations()
        sys.exit(0)
    if args.stats:
        weekly_stats_digest()
        sys.exit(0)

    if not args.url:
        parser.print_help()
        sys.exit(1)

    url = args.url
    dry_run = args.dry_run
    do_email = args.email
    eco_filter = args.ecosystem
    user_id = args.user_id

    # Parse URL
    info = parse_github_url(url)
    if not info:
        print(f"[migrator] Invalid GitHub URL: {url}")
        sys.exit(1)

    print(f"[migrator] Repo: {info['owner']}/{info['repo']} (branch: {info['branch']})")
    print(f"[migrator] User: {user_id} | Dry run: {dry_run}")

    # Fetch tree
    tree = fetch_repo_tree(info["owner"], info["repo"], info["branch"])
    if not tree:
        print("[migrator] Failed to fetch repo tree (check URL or rate limit)")
        sys.exit(1)
    print(f"[migrator] Files in repo: {len(tree)}")

    # Detect context (with proper owner/repo/branch params)
    ctx = detect_context(tree, info["owner"], info["repo"], info["branch"])
    print(f"[migrator] Project type: {ctx['type']} (framework: {ctx.get('framework', 'none')})")

    # Filter contracts
    contracts = filter_contract_files(tree)
    if eco_filter:
        contracts = [c for c in contracts if c["ecosystem"] == eco_filter]
    print(f"[migrator] Contract files found: {len(contracts)}")

    if not contracts:
        print("[migrator] No contract files found in this repo")
        sys.exit(0)

    # Process each contract
    results = {
        "imported": 0, "failed": 0, "skipped": 0,
        "details": [], "ecosystems": set(), "dangerous": [],
    }
    imported_names = []

    for cf in contracts:
        path = cf["path"]
        ecosystem = cf["ecosystem"]
        print(f"\n  Processing: {path} ({ecosystem})")
        results["ecosystems"].add(ecosystem)

        # Fetch file content
        source = fetch_file(info["owner"], info["repo"], info["branch"], path)
        if not source:
            print(f"    SKIP: Could not fetch file")
            results["skipped"] += 1
            continue

        # ── Compile/parse based on ecosystem ──
        compiled = {"success": False, "contracts": {}, "errors": []}

        if ecosystem == "solidity":
            compiled = compile_solidity(source, Path(path).name)
        elif ecosystem == "vyper":
            compiled = compile_vyper(source, Path(path).name)
        elif ecosystem == "abi_json":
            compiled = parse_abi_json(source)
        elif ecosystem == "rust":
            # Disambiguate: Anchor vs Soroban vs generic
            if ctx["type"] == "solana_anchor":
                compiled = parse_anchor_rs(source, Path(path).name)
            else:
                compiled = llm_parse_contract(source, ecosystem, Path(path).name)
        elif ecosystem in ("move", "clarity", "teal"):
            compiled = llm_parse_contract(source, ecosystem, Path(path).name)
        else:
            compiled = llm_parse_contract(source, ecosystem, Path(path).name)

        if not compiled["success"]:
            print(f"    WARN: {compiled['errors'][:2]}")
            results["failed"] += 1
            results["details"].append({
                "path": path, "status": "failed", "ecosystem": ecosystem,
                "errors": compiled["errors"][:3],
            })
            continue

        # Process each contract found in the file
        for name, data in compiled["contracts"].items():
            abi = data.get("abi", [])
            fn_count = sum(1 for f in abi if f.get("type") == "function")
            event_count = sum(1 for f in abi if f.get("type") == "event")

            # Generate SDK
            sdk = generate_sdk(name, abi, source)
            category = detect_category(abi)

            # Detect dangerous patterns in source
            dangerous = detect_dangerous_patterns(source)

            print(f"    Contract: {name}")
            print(f"      Functions: {fn_count} ({sdk['public_count']} public, {sdk['owner_count']} owner)")
            print(f"      Events: {event_count} | Category: {category}")
            if dangerous:
                print(f"      DANGEROUS: {', '.join(dangerous)}")
                results["dangerous"].extend([f"{name}:{p}" for p in dangerous])

            # Import to GROOT Brain (unless dry run)
            if not dry_run:
                import_result = import_to_groot_brain(
                    user_id=user_id,
                    repo_info=info,
                    contract_name=name,
                    abi=abi,
                    sdk=sdk,
                    category=category,
                    ecosystem=ecosystem,
                    dangerous_patterns=dangerous,
                    source_path=path,
                )
                if import_result["imported"]:
                    print(f"      -> Imported to GROOT Brain (project: {import_result.get('project_id', 'n/a')})")
                    imported_names.append(name)
                else:
                    print(f"      -> Import issues: {import_result['errors'][:2]}")

            results["imported"] += 1
            results["details"].append({
                "path": path, "contract": name, "status": "imported",
                "functions": fn_count, "public": sdk["public_count"],
                "owner_only": sdk["owner_count"], "events": event_count,
                "category": category, "ecosystem": ecosystem,
                "dangerous": dangerous,
            })

    # ── Post-import delegation ──
    if imported_names and not dry_run:
        delegate_cag_sync(imported_names)
        delegate_security_scan(imported_names)

    # ── Save migration job for retry/stats tracking ──
    job = {
        "url": url,
        "repo": f"{info['owner']}/{info['repo']}",
        "user_id": user_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "imported": results["imported"],
        "failed": results["failed"],
        "skipped": results["skipped"],
        "ecosystems": sorted(results["ecosystems"]),
        "status": "failed" if results["failed"] > 0 and results["imported"] == 0 else
                  "partial" if results["failed"] > 0 else "complete",
        "dangerous_count": len(results["dangerous"]),
    }
    if not dry_run:
        save_migration_job(job)

    # ── Summary ──
    print(f"\n{'=' * 60}")
    print(f"Migration {'(DRY RUN) ' if dry_run else ''}complete:")
    print(f"  Imported: {results['imported']}")
    print(f"  Failed:   {results['failed']}")
    print(f"  Skipped:  {results['skipped']}")
    print(f"  Repo:     {info['owner']}/{info['repo']}")
    if results["dangerous"]:
        print(f"  Dangerous patterns: {len(results['dangerous'])} found")
    if imported_names and not dry_run:
        print(f"  Delegated: CAG sync + security scan for {len(imported_names)} contract(s)")

    # ── Email report ──
    if do_email:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        rows = ""
        for d in results["details"]:
            color = "#00d4aa" if d["status"] == "imported" else "#ff6b6b"
            name_cell = d.get("contract", Path(d["path"]).name)
            danger_badge = f" <span style='color:#ff6b6b'>({len(d.get('dangerous', []))} dangerous)</span>" if d.get("dangerous") else ""
            rows += (
                f"<tr>"
                f"<td style='padding:6px;color:{color}'>{d['status']}</td>"
                f"<td style='padding:6px'>{name_cell}{danger_badge}</td>"
                f"<td style='padding:6px'>{d.get('ecosystem', '-')}</td>"
                f"<td style='padding:6px'>{d.get('functions', '-')}</td>"
                f"<td style='padding:6px'>{d.get('category', '-')}</td>"
                f"</tr>"
            )
        html = f"""<div style="font-family:sans-serif;max-width:700px;margin:0 auto">
          <div style="background:#1a1a2e;color:#e0e0e0;padding:16px 20px;border-radius:8px 8px 0 0">
            <h2 style="margin:0;font-size:18px">Repo Migration — {info['owner']}/{info['repo']}</h2>
            <p style="margin:4px 0 0;font-size:12px;color:#888">{ts} | User: {user_id}</p></div>
          <div style="background:#16213e;color:#e0e0e0;padding:20px;border-radius:0 0 8px 8px">
            <p><strong>{results['imported']}</strong> imported, <strong>{results['failed']}</strong> failed, <strong>{results['skipped']}</strong> skipped</p>
            {'<p style="color:#ff6b6b">Dangerous patterns detected: ' + ', '.join(results["dangerous"]) + '</p>' if results["dangerous"] else ''}
            <table style="width:100%;border-collapse:collapse">
              <tr style="border-bottom:1px solid #333"><th style="padding:6px;text-align:left">Status</th><th style="padding:6px;text-align:left">Contract</th><th style="padding:6px;text-align:left">Ecosystem</th><th style="padding:6px;text-align:left">Functions</th><th style="padding:6px;text-align:left">Category</th></tr>
              {rows}
            </table>
            <hr style="border:none;border-top:1px solid #333;margin:16px 0">
            <p style="font-size:11px;color:#666">GROOT Repo Migrator Agent</p></div></div>"""
        send_email(
            f"[REFINET REGISTRY] Migration: {info['owner']}/{info['repo']} — {ts}",
            html,
            json.dumps({"summary": job, "details": results["details"]}, indent=2, default=str),
        )

    # Output JSON results
    results["ecosystems"] = sorted(results["ecosystems"])
    print(json.dumps({"summary": job if not dry_run else {}, "details": results["details"]}, indent=2, default=str))
    sys.exit(0 if results["failed"] == 0 else 1)


if __name__ == "__main__":
    main()

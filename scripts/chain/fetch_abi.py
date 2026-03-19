#!/usr/bin/env python3
"""
Fetch a verified contract ABI from block explorer APIs (Etherscan, Basescan, etc).
Outputs the ABI JSON to stdout and optionally saves to a file.

Usage:
    python scripts/chain/fetch_abi.py

Environment:
    SCRIPT_ARGS: JSON {"chain": "ethereum", "address": "0x...", "api_key": "optional"}
"""

import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "fetch_abi",
    "description": "Fetch verified contract ABI from Etherscan/Basescan/Arbiscan block explorer APIs",
    "category": "chain",
    "requires_admin": False,
}

# Block explorer API endpoints
EXPLORER_APIS = {
    "ethereum": "https://api.etherscan.io/api",
    "base": "https://api.basescan.org/api",
    "arbitrum": "https://api.arbiscan.io/api",
    "polygon": "https://api.polygonscan.com/api",
    "sepolia": "https://api-sepolia.etherscan.io/api",
}


def fetch_abi(chain: str, address: str, api_key: str = "") -> dict:
    """Fetch ABI from block explorer API. Returns {"abi": [...], "name": "...", "error": None}."""
    api_url = EXPLORER_APIS.get(chain)
    if not api_url:
        return {"abi": None, "name": None, "error": f"No explorer API for chain '{chain}'"}

    # Fetch ABI
    params = f"?module=contract&action=getabi&address={address}"
    if api_key:
        params += f"&apikey={api_key}"

    try:
        req = urllib.request.Request(f"{api_url}{params}", method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return {"abi": None, "name": None, "error": f"API request failed: {e}"}

    if data.get("status") != "1":
        msg = data.get("result", data.get("message", "Unknown error"))
        return {"abi": None, "name": None, "error": f"Explorer API error: {msg}"}

    try:
        abi = json.loads(data["result"])
    except json.JSONDecodeError:
        return {"abi": None, "name": None, "error": "Invalid ABI JSON in response"}

    # Try to get contract name via getsourcecode
    contract_name = None
    try:
        src_params = f"?module=contract&action=getsourcecode&address={address}"
        if api_key:
            src_params += f"&apikey={api_key}"
        req2 = urllib.request.Request(f"{api_url}{src_params}", method="GET")
        with urllib.request.urlopen(req2, timeout=15) as resp2:
            src_data = json.loads(resp2.read().decode())
        if src_data.get("status") == "1" and src_data.get("result"):
            contract_name = src_data["result"][0].get("ContractName", "")
    except Exception:
        pass

    return {"abi": abi, "name": contract_name, "error": None}


def main():
    args = json.loads(os.environ.get("SCRIPT_ARGS", "{}"))
    chain = args.get("chain", "ethereum")
    address = args.get("address", "")
    api_key = args.get("api_key", "")
    save_path = args.get("save_to", "")

    if not address:
        print("ERROR: 'address' is required in SCRIPT_ARGS")
        print('Example: SCRIPT_ARGS=\'{"chain":"ethereum","address":"0xdAC17F958D2ee523a2206206994597C13D831ec7"}\'')
        sys.exit(1)

    print(f"Fetching ABI for {address} on {chain}...")

    result = fetch_abi(chain, address, api_key)

    if result["error"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    abi = result["abi"]
    name = result["name"] or "Unknown"

    # Count functions and events
    functions = [item for item in abi if item.get("type") == "function"]
    events = [item for item in abi if item.get("type") == "event"]

    print(f"\n=== {name} ({address[:10]}...{address[-6:]}) ===")
    print(f"Chain: {chain}")
    print(f"Functions: {len(functions)}")
    print(f"Events: {len(events)}")

    # List function signatures
    if functions:
        print("\nFunctions:")
        for fn in functions:
            inputs = ", ".join(f"{i.get('type', '?')} {i.get('name', '?')}" for i in fn.get("inputs", []))
            mut = fn.get("stateMutability", "")
            print(f"  {fn['name']}({inputs}) [{mut}]")

    if events:
        print("\nEvents:")
        for ev in events:
            inputs = ", ".join(f"{i.get('type', '?')} {i.get('name', '?')}" for i in ev.get("inputs", []))
            print(f"  {ev['name']}({inputs})")

    # Save to file if requested
    if save_path:
        with open(save_path, "w") as f:
            json.dump(abi, f, indent=2)
        print(f"\nABI saved to: {save_path}")

    # Always output the ABI JSON at the end for programmatic use
    print(f"\n--- ABI JSON ({len(abi)} entries) ---")
    print(json.dumps(abi, indent=2)[:2000])  # Cap output for script runner
    if len(json.dumps(abi)) > 2000:
        print(f"... (truncated, full ABI is {len(json.dumps(abi))} bytes)")


if __name__ == "__main__":
    main()

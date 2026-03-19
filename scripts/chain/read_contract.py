#!/usr/bin/env python3
"""
Read a smart contract's public state via JSON-RPC.
Calls common read functions: name, symbol, decimals, totalSupply, balanceOf, owner.

Usage:
    python scripts/chain/read_contract.py

Environment:
    SCRIPT_ARGS: JSON {"chain": "ethereum", "address": "0x...", "functions": ["name", "symbol"]}
"""

import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "read_contract",
    "description": "Read a contract's public state (name, symbol, totalSupply, owner, balanceOf) via RPC",
    "category": "chain",
    "requires_admin": False,
}

DEFAULT_RPCS = {
    "ethereum": "https://eth.llamarpc.com",
    "base": "https://mainnet.base.org",
    "arbitrum": "https://arb1.arbitrum.io/rpc",
    "polygon": "https://polygon-rpc.com",
    "sepolia": "https://rpc.sepolia.org",
}

# Common ERC20/ERC721 function selectors (first 4 bytes of keccak256)
SELECTORS = {
    "name":         "0x06fdde03",
    "symbol":       "0x95d89b41",
    "decimals":     "0x313ce567",
    "totalSupply":  "0x18160ddd",
    "owner":        "0x8da5cb5b",
    "paused":       "0x5c975abb",
}


def eth_call(rpc_url: str, to: str, data: str) -> str:
    """Execute eth_call and return raw hex result."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{"to": to, "data": data}, "latest"],
        "id": 1,
    }).encode()

    req = urllib.request.Request(
        rpc_url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode())

    if "error" in result:
        return f"ERROR: {result['error'].get('message', 'unknown')}"
    return result.get("result", "0x")


def decode_string(hex_data: str) -> str:
    """Decode ABI-encoded string from hex."""
    if not hex_data or hex_data == "0x" or len(hex_data) < 130:
        return ""
    try:
        # Skip 0x + 32-byte offset + 32-byte length
        length = int(hex_data[66:130], 16)
        string_hex = hex_data[130:130 + length * 2]
        return bytes.fromhex(string_hex).decode("utf-8", errors="replace").rstrip("\x00")
    except Exception:
        return hex_data[:20] + "..."


def decode_uint256(hex_data: str) -> int:
    """Decode uint256 from hex."""
    if not hex_data or hex_data == "0x":
        return 0
    try:
        return int(hex_data, 16)
    except Exception:
        return 0


def decode_address(hex_data: str) -> str:
    """Decode address from hex (last 20 bytes of 32-byte word)."""
    if not hex_data or hex_data == "0x" or len(hex_data) < 42:
        return "0x" + "0" * 40
    return "0x" + hex_data[-40:]


def main():
    args = json.loads(os.environ.get("SCRIPT_ARGS", "{}"))
    chain = args.get("chain", "ethereum")
    address = args.get("address", "")
    functions = args.get("functions", list(SELECTORS.keys()))

    if not address:
        print("ERROR: 'address' is required in SCRIPT_ARGS")
        print('Example: SCRIPT_ARGS=\'{"chain":"ethereum","address":"0xdAC17F958D2ee523a2206206994597C13D831ec7"}\'')
        sys.exit(1)

    rpc_url = args.get("rpc_url", DEFAULT_RPCS.get(chain, ""))
    if not rpc_url:
        print(f"ERROR: No RPC URL for chain '{chain}'")
        sys.exit(1)

    print(f"=== Contract State: {address} ===")
    print(f"Chain: {chain}")
    print(f"RPC: {rpc_url}")
    print()

    for fn_name in functions:
        selector = SELECTORS.get(fn_name)
        if not selector:
            print(f"  {fn_name}: unknown selector (skipped)")
            continue

        raw = eth_call(rpc_url, address, selector)

        if raw.startswith("ERROR"):
            print(f"  {fn_name}: {raw}")
            continue

        # Decode based on expected return type
        if fn_name in ("name", "symbol"):
            value = decode_string(raw)
        elif fn_name == "owner":
            value = decode_address(raw)
        elif fn_name == "paused":
            value = "true" if decode_uint256(raw) == 1 else "false"
        else:
            value = decode_uint256(raw)
            if fn_name == "totalSupply":
                # Show both raw and human-readable (assuming 18 decimals)
                human = value / (10 ** 18)
                value = f"{value} (≈ {human:,.2f} if 18 decimals)"

        print(f"  {fn_name}: {value}")

    # Also fetch ETH balance of the contract
    balance_payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "eth_getBalance",
        "params": [address, "latest"],
        "id": 2,
    }).encode()
    try:
        req = urllib.request.Request(
            rpc_url, data=balance_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
        balance_wei = int(result.get("result", "0x0"), 16)
        balance_eth = balance_wei / (10 ** 18)
        print(f"\n  ETH balance: {balance_eth:.6f} ETH ({balance_wei} wei)")
    except Exception as e:
        print(f"\n  ETH balance: ERROR ({e})")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
One-shot balance and nonce check for a wallet or contract address.
Reports ETH balance, transaction count, and whether it's a contract or EOA.

Usage:
    python scripts/chain/monitor_address.py

Environment:
    SCRIPT_ARGS: JSON {"chain": "ethereum", "address": "0x..."}
"""

import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

SCRIPT_META = {
    "name": "monitor_address",
    "description": "Check wallet balance, nonce, and contract/EOA status for an address",
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


def rpc_call(rpc_url: str, method: str, params: list):
    """Make a JSON-RPC call and return the result."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1,
    }).encode()

    req = urllib.request.Request(
        rpc_url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())

    if "error" in data:
        raise RuntimeError(data["error"].get("message", "RPC error"))
    return data.get("result")


def main():
    args = json.loads(os.environ.get("SCRIPT_ARGS", "{}"))
    chain = args.get("chain", "ethereum")
    address = args.get("address", "")

    if not address:
        print("ERROR: 'address' is required in SCRIPT_ARGS")
        print('Example: SCRIPT_ARGS=\'{"chain":"ethereum","address":"0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"}\'')
        sys.exit(1)

    rpc_url = args.get("rpc_url", DEFAULT_RPCS.get(chain, ""))
    if not rpc_url:
        print(f"ERROR: No RPC URL for chain '{chain}'")
        sys.exit(1)

    print(f"=== Address Monitor: {address} ===")
    print(f"Chain: {chain}")
    print()

    # 1. Get ETH balance
    try:
        balance_hex = rpc_call(rpc_url, "eth_getBalance", [address, "latest"])
        balance_wei = int(balance_hex, 16)
        balance_eth = balance_wei / (10 ** 18)
        print(f"  Balance: {balance_eth:.6f} ETH")
        print(f"  Balance (wei): {balance_wei}")
    except Exception as e:
        print(f"  Balance: ERROR ({e})")

    # 2. Get transaction count (nonce)
    try:
        nonce_hex = rpc_call(rpc_url, "eth_getTransactionCount", [address, "latest"])
        nonce = int(nonce_hex, 16)
        print(f"  Nonce (tx count): {nonce}")
    except Exception as e:
        print(f"  Nonce: ERROR ({e})")

    # 3. Check if it's a contract (has code) or EOA
    try:
        code = rpc_call(rpc_url, "eth_getCode", [address, "latest"])
        is_contract = code and code != "0x" and code != "0x0"
        addr_type = "Contract" if is_contract else "EOA (Externally Owned Account)"
        print(f"  Type: {addr_type}")
        if is_contract:
            code_size = (len(code) - 2) // 2  # Remove 0x prefix, divide by 2 for bytes
            print(f"  Code size: {code_size} bytes")
    except Exception as e:
        print(f"  Type: ERROR ({e})")

    # 4. Get current block number for context
    try:
        block_hex = rpc_call(rpc_url, "eth_blockNumber", [])
        block_num = int(block_hex, 16)
        print(f"\n  Current block: {block_num:,}")
    except Exception as e:
        print(f"\n  Current block: ERROR ({e})")

    # 5. Get gas price
    try:
        gas_hex = rpc_call(rpc_url, "eth_gasPrice", [])
        gas_wei = int(gas_hex, 16)
        gas_gwei = gas_wei / (10 ** 9)
        print(f"  Gas price: {gas_gwei:.2f} Gwei")
    except Exception as e:
        print(f"  Gas price: ERROR ({e})")


if __name__ == "__main__":
    main()

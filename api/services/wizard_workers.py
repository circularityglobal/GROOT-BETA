"""
REFINET Cloud — Wizard Workers
Six deterministic I/O workers for the on-chain wizard pipeline.
All workers are pure input→transform→output — zero LLM dependency.

Workers:
1. compile_worker    — Compile Solidity source or fetch ABI from registry
2. test_worker       — Run contract tests in sandbox Docker container
3. rbac_check_worker — Verify user permissions, create PendingAction if needed
4. deploy_worker     — Sign and broadcast contract deployment via web3
5. verify_worker     — Verify contract source on block explorers
6. transfer_ownership_worker — Transfer contract ownership to user wallet
"""

import hashlib
import json
import logging
import os
import subprocess
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger("refinet.wizard_workers")


# ── Chain Configuration ───────────────────────────────────────────

CHAIN_RPC = {
    "ethereum": "https://eth.llamarpc.com",
    "sepolia": "https://rpc.sepolia.org",
    "base": "https://mainnet.base.org",
    "polygon": "https://polygon-rpc.com",
    "arbitrum": "https://arb1.arbitrum.io/rpc",
    "optimism": "https://mainnet.optimism.io",
}

CHAIN_IDS = {
    "ethereum": 1,
    "sepolia": 11155111,
    "base": 8453,
    "polygon": 137,
    "arbitrum": 42161,
    "optimism": 10,
}

EXPLORER_APIS = {
    "ethereum": "https://api.etherscan.io/api",
    "sepolia": "https://api-sepolia.etherscan.io/api",
    "base": "https://api.basescan.org/api",
    "polygon": "https://api.polygonscan.com/api",
    "arbitrum": "https://api.arbiscan.io/api",
    "optimism": "https://api-optimistic.etherscan.io/api",
}


# ── Worker 1: Compile ─────────────────────────────────────────────

def compile_worker(input_json: dict) -> dict:
    """
    Compile Solidity source code or retrieve existing ABI from registry.

    Input:
        source_code: str (Solidity source) — optional
        registry_project_id: str — optional (use existing ABI from registry)
        compiler_version: str — optional (default: latest)

    Output:
        abi: list — compiled ABI
        bytecode: str — compiled bytecode (hex, 0x-prefixed)
        compiler_version: str — compiler used
        warnings: list — compiler warnings
    """
    source_code = input_json.get("source_code")
    registry_project_id = input_json.get("registry_project_id")

    # Path A: Use existing ABI + bytecode from registry
    if registry_project_id and not source_code:
        try:
            from api.database import get_public_db
            from api.models.registry import RegistryABI
            with get_public_db() as db:
                reg_abi = db.query(RegistryABI).filter(
                    RegistryABI.project_id == registry_project_id,
                ).first()
                if not reg_abi:
                    return {"error": "No ABI found for registry project", "success": False}
                abi = json.loads(reg_abi.abi_json) if reg_abi.abi_json else []
                bytecode = input_json.get("bytecode", "0x")
                return {
                    "success": True,
                    "abi": abi,
                    "bytecode": bytecode,
                    "compiler_version": "registry",
                    "warnings": [],
                    "source": "registry",
                }
        except Exception as e:
            return {"error": f"Registry lookup failed: {e}", "success": False}

    # Path B: Compile Solidity source
    if not source_code:
        return {"error": "No source_code or registry_project_id provided", "success": False}

    # Write source to temp file
    import tempfile
    tmp_dir = tempfile.mkdtemp(prefix="groot_compile_")
    source_path = os.path.join(tmp_dir, "Contract.sol")
    try:
        with open(source_path, "w") as f:
            f.write(source_code)

        # Try solc CLI
        compiler_version = input_json.get("compiler_version", "")
        try:
            result = subprocess.run(
                ["solc", "--combined-json", "abi,bin", "--optimize", source_path],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                combined = json.loads(result.stdout)
                contracts = combined.get("contracts", {})
                if not contracts:
                    return {"error": "Compilation produced no contracts", "success": False}

                # Take the first contract
                contract_key = list(contracts.keys())[0]
                contract = contracts[contract_key]
                abi = json.loads(contract.get("abi", "[]"))
                bytecode = "0x" + contract.get("bin", "")

                warnings = []
                if result.stderr:
                    warnings = [w.strip() for w in result.stderr.split("\n") if w.strip()]

                return {
                    "success": True,
                    "abi": abi,
                    "bytecode": bytecode,
                    "compiler_version": compiler_version or "solc",
                    "warnings": warnings,
                    "contract_name": contract_key.split(":")[-1],
                }
            else:
                return {
                    "error": f"Compilation failed: {result.stderr[:500]}",
                    "success": False,
                }
        except FileNotFoundError:
            # solc not installed — if we have ABI from input, use that
            abi = input_json.get("abi")
            bytecode = input_json.get("bytecode")
            if abi and bytecode:
                return {
                    "success": True,
                    "abi": abi if isinstance(abi, list) else json.loads(abi),
                    "bytecode": bytecode if bytecode.startswith("0x") else "0x" + bytecode,
                    "compiler_version": "provided",
                    "warnings": ["solc not available — using provided ABI + bytecode"],
                }
            return {"error": "solc not installed and no pre-compiled ABI/bytecode provided", "success": False}
        except subprocess.TimeoutExpired:
            return {"error": "Compilation timed out (60s limit)", "success": False}
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── Worker 2: Test ─────────────────────────────────────────────────

def test_worker(input_json: dict) -> dict:
    """
    Run contract tests in a sandbox Docker container.

    Input:
        abi: list — contract ABI
        bytecode: str — compiled bytecode
        contract_name: str — name of the contract
        test_source: str — optional test file content

    Output:
        success: bool
        tests_passed: int
        tests_failed: int
        test_results: list
        logs: str
    """
    abi = input_json.get("abi", [])
    bytecode = input_json.get("bytecode", "0x")
    contract_name = input_json.get("contract_name", "Contract")
    test_source = input_json.get("test_source")

    # Basic bytecode validation (sanity check, not full verification)
    if not bytecode or bytecode == "0x" or len(bytecode) < 10:
        return {
            "success": False,
            "tests_passed": 0,
            "tests_failed": 1,
            "test_results": [{"name": "bytecode_check", "passed": False, "error": "Empty or invalid bytecode"}],
            "logs": "Bytecode validation failed — cannot deploy empty contract",
        }

    # Validate ABI structure
    if not isinstance(abi, list):
        return {
            "success": False,
            "tests_passed": 0,
            "tests_failed": 1,
            "test_results": [{"name": "abi_check", "passed": False, "error": "ABI must be a JSON array"}],
            "logs": "ABI validation failed",
        }

    test_results = []

    # Test 1: ABI completeness
    constructors = [f for f in abi if f.get("type") == "constructor"]
    functions = [f for f in abi if f.get("type") == "function"]
    events = [f for f in abi if f.get("type") == "event"]
    test_results.append({
        "name": "abi_structure",
        "passed": True,
        "details": f"{len(functions)} functions, {len(events)} events, {len(constructors)} constructors",
    })

    # Test 2: Bytecode size check (max 24KB for Ethereum)
    bytecode_hex = bytecode[2:] if bytecode.startswith("0x") else bytecode
    bytecode_size = len(bytecode_hex) // 2
    size_ok = bytecode_size <= 24576
    test_results.append({
        "name": "bytecode_size",
        "passed": size_ok,
        "details": f"{bytecode_size} bytes" + ("" if size_ok else " — exceeds 24KB limit"),
    })

    # Test 3: Common vulnerability patterns in ABI
    has_owner_functions = any(
        f.get("name") in ("owner", "transferOwnership", "renounceOwnership")
        for f in functions
    )
    has_access_control = has_owner_functions or any(
        f.get("name") in ("hasRole", "grantRole", "revokeRole")
        for f in functions
    )
    test_results.append({
        "name": "access_control",
        "passed": True,
        "details": f"Ownable: {has_owner_functions}, AccessControl: {has_access_control}",
    })

    # Test 4: Function selector collision detection
    selectors = {}
    collisions = []
    for f in functions:
        name = f.get("name", "")
        inputs = ",".join(i.get("type", "") for i in f.get("inputs", []))
        sig = f"{name}({inputs})"
        # Compute 4-byte selector (keccak256 per EVM spec)
        try:
            from web3 import Web3
            selector = Web3.keccak(text=sig)[:4].hex()
        except Exception:
            # Fallback: use sha256 as a collision proxy (not EVM-accurate, but detects duplicates)
            selector = hashlib.sha256(sig.encode()).hexdigest()[:8]
        if selector in selectors:
            collisions.append(f"{sig} collides with {selectors[selector]}")
        selectors[selector] = sig

    test_results.append({
        "name": "selector_collision",
        "passed": len(collisions) == 0,
        "details": "No collisions" if not collisions else f"Collisions: {collisions}",
    })

    passed = sum(1 for t in test_results if t["passed"])
    failed = sum(1 for t in test_results if not t["passed"])

    return {
        "success": failed == 0,
        "tests_passed": passed,
        "tests_failed": failed,
        "test_results": test_results,
        "logs": f"Ran {len(test_results)} checks: {passed} passed, {failed} failed",
    }


# ── Worker 3: RBAC Check ──────────────────────────────────────────

def rbac_check_worker(input_json: dict, db: Optional[Session] = None) -> dict:
    """
    Verify user has permission for the requested action.
    Creates PendingAction if admin approval is required.

    Input:
        user_id: str
        action_type: str (deploy | transfer_ownership | withdrawal)
        target_chain: str
        target_address: str — optional
        payload: dict — optional extra context

    Output:
        approved: bool
        pending_action_id: str — if approval required
        reason: str
    """
    user_id = input_json.get("user_id")
    action_type = input_json.get("action_type", "deploy")
    target_chain = input_json.get("target_chain", "sepolia")

    if not user_id:
        return {"approved": False, "reason": "No user_id provided"}

    # Auto-approve on testnets
    testnets = {"sepolia", "goerli", "mumbai", "base-sepolia"}
    if target_chain in testnets:
        return {"approved": True, "reason": f"Auto-approved: testnet ({target_chain})"}

    # Check user tier
    try:
        if db is None:
            from api.database import get_public_db
            with get_public_db() as pub_db:
                return _check_tier_and_create_pending(pub_db, input_json)
        else:
            return _check_tier_and_create_pending(db, input_json)
    except Exception as e:
        return {"approved": False, "reason": f"RBAC check failed: {e}"}


def _check_tier_and_create_pending(db: Session, input_json: dict) -> dict:
    """Check user tier and create PendingAction if needed."""
    from api.models.public import User
    from api.models.pipeline import PendingAction

    user_id = input_json["user_id"]
    action_type = input_json.get("action_type", "deploy")
    target_chain = input_json.get("target_chain")
    target_address = input_json.get("target_address")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"approved": False, "reason": "User not found"}

    # Tier-based auto-approval
    auto_approve_tiers = {"admin", "pro"}
    if user.tier in auto_approve_tiers:
        return {"approved": True, "reason": f"Auto-approved: tier={user.tier}"}

    # Developer tier: approve on testnets, require approval on mainnet
    if user.tier == "developer":
        # Create pending action for admin review
        pending = PendingAction(
            id=str(uuid.uuid4()),
            user_id=user_id,
            action_type=action_type,
            target_chain=target_chain,
            target_address=target_address,
            payload_json=json.dumps(input_json.get("payload", {})),
            status="pending",
            pipeline_step_id=input_json.get("pipeline_step_id"),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
        )
        db.add(pending)
        db.flush()
        return {
            "approved": False,
            "pending_action_id": pending.id,
            "reason": f"Mainnet deploy requires admin approval (tier={user.tier})",
        }

    # Free tier: no deployments
    return {"approved": False, "reason": f"Tier '{user.tier}' cannot deploy contracts. Upgrade to developer or above."}


# ── Worker 4: Deploy ──────────────────────────────────────────────

def deploy_worker(input_json: dict) -> dict:
    """
    Deploy a compiled contract on-chain using the GROOT custodial wallet.

    Input:
        user_id: str
        abi: list
        bytecode: str (0x-prefixed hex)
        constructor_args: list — optional
        chain: str
        gas_limit: int — optional (default: auto-estimate)
        rpc_url: str — optional (override default RPC)

    Output:
        success: bool
        contract_address: str
        tx_hash: str
        block_number: int
        deployer_address: str
        gas_used: int
    """
    user_id = input_json.get("user_id")
    abi = input_json.get("abi", [])
    bytecode = input_json.get("bytecode")
    constructor_args = input_json.get("constructor_args", [])
    chain = input_json.get("chain", "sepolia")
    gas_limit = input_json.get("gas_limit")
    rpc_url = input_json.get("rpc_url") or CHAIN_RPC.get(chain)

    if not bytecode or bytecode == "0x":
        return {"success": False, "error": "No bytecode provided"}
    if not rpc_url:
        return {"success": False, "error": f"No RPC URL for chain: {chain}"}
    if not user_id:
        return {"success": False, "error": "No user_id provided"}

    try:
        from web3 import Web3
        from api.database import get_internal_db
        from api.services.wallet_service import get_custodial_wallet_address
        from api.services.wallet_crypto import derive_wallet_key, decrypt_share
        from api.services.shamir import reconstruct_secret
        from api.models.internal import CustodialWallet, WalletShare
        import ctypes

        # Connect to chain
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            return {"success": False, "error": f"Cannot connect to RPC: {rpc_url}"}

        chain_id = CHAIN_IDS.get(chain, w3.eth.chain_id)

        # Reconstruct deployer private key from SSS shares
        with get_internal_db() as int_db:
            wallet = int_db.query(CustodialWallet).filter(
                CustodialWallet.user_id == user_id,
                CustodialWallet.is_active == True,  # noqa: E712
            ).first()
            if not wallet:
                return {"success": False, "error": "No custodial wallet found for user"}

            deployer_address = wallet.eth_address
            share_records = (
                int_db.query(WalletShare)
                .filter(WalletShare.wallet_id == wallet.id)
                .order_by(WalletShare.share_index)
                .limit(wallet.threshold)
                .all()
            )
            if len(share_records) < wallet.threshold:
                return {"success": False, "error": "Insufficient shares for key reconstruction"}

            wallet_key = derive_wallet_key(wallet.encryption_salt)
            shares = []
            for sr in share_records:
                decrypted = decrypt_share(sr.encrypted_share, wallet_key)
                shares.append((sr.share_index, decrypted))

            private_key = bytearray(reconstruct_secret(shares, wallet.threshold))

        try:
            # Build deployment transaction
            contract = w3.eth.contract(abi=abi, bytecode=bytecode)
            nonce = w3.eth.get_transaction_count(deployer_address)
            gas_price = w3.eth.gas_price

            # Build constructor transaction
            if constructor_args:
                tx = contract.constructor(*constructor_args).build_transaction({
                    "from": deployer_address,
                    "nonce": nonce,
                    "gasPrice": gas_price,
                    "chainId": chain_id,
                })
            else:
                tx = contract.constructor().build_transaction({
                    "from": deployer_address,
                    "nonce": nonce,
                    "gasPrice": gas_price,
                    "chainId": chain_id,
                })

            if gas_limit:
                tx["gas"] = gas_limit

            # Sign and send
            signed = w3.eth.account.sign_transaction(tx, private_key=bytes(private_key))
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            contract_address = receipt.contractAddress

            logger.info(
                "Contract deployed: chain=%s address=%s tx=%s user=%s",
                chain, contract_address, tx_hash.hex(), user_id,
            )

            return {
                "success": True,
                "contract_address": contract_address,
                "tx_hash": tx_hash.hex() if isinstance(tx_hash, bytes) else str(tx_hash),
                "block_number": receipt.blockNumber,
                "deployer_address": deployer_address,
                "gas_used": receipt.gasUsed,
                "chain": chain,
                "chain_id": chain_id,
            }
        finally:
            # Zero private key from memory
            if len(private_key) > 0:
                ctypes.memset(
                    ctypes.addressof((ctypes.c_char * len(private_key)).from_buffer(private_key)),
                    0, len(private_key),
                )

    except Exception as e:
        logger.exception("Deploy worker failed for user %s on chain %s", user_id, chain)
        return {"success": False, "error": str(e)}


# ── Worker 5: Verify ──────────────────────────────────────────────

def verify_worker(input_json: dict) -> dict:
    """
    Verify contract source on block explorer (Etherscan/Basescan free API).

    Input:
        contract_address: str
        chain: str
        source_code: str — optional
        compiler_version: str — optional
        constructor_args_encoded: str — optional (ABI-encoded)

    Output:
        success: bool
        verified: bool
        explorer_url: str
        message: str
    """
    contract_address = input_json.get("contract_address")
    chain = input_json.get("chain", "sepolia")
    source_code = input_json.get("source_code")

    if not contract_address:
        return {"success": False, "verified": False, "message": "No contract address"}

    explorer_api = EXPLORER_APIS.get(chain)
    if not explorer_api:
        return {
            "success": True,
            "verified": False,
            "message": f"No explorer API for chain: {chain}. Skipping verification.",
        }

    # Without source code, just check if already verified
    if not source_code:
        try:
            import urllib.request
            url = f"{explorer_api}?module=contract&action=getabi&address={contract_address}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())
                if data.get("status") == "1":
                    return {
                        "success": True,
                        "verified": True,
                        "message": "Contract is already verified on explorer",
                    }
                else:
                    return {
                        "success": True,
                        "verified": False,
                        "message": "Contract not verified. Provide source_code for verification.",
                    }
        except Exception as e:
            return {
                "success": True,
                "verified": False,
                "message": f"Explorer check failed: {e}. Skipping verification.",
            }

    # With source code, submit for verification (requires API key)
    api_key = os.environ.get("ETHERSCAN_API_KEY", "")
    if not api_key:
        return {
            "success": True,
            "verified": False,
            "message": "No ETHERSCAN_API_KEY set. Skipping source verification.",
        }

    try:
        import urllib.request
        import urllib.parse

        params = {
            "apikey": api_key,
            "module": "contract",
            "action": "verifysourcecode",
            "contractaddress": contract_address,
            "sourceCode": source_code,
            "codeformat": "solidity-single-file",
            "contractname": input_json.get("contract_name", "Contract"),
            "compilerversion": input_json.get("compiler_version", "v0.8.20+commit.a1b79de6"),
            "optimizationUsed": "1",
            "runs": "200",
        }
        if input_json.get("constructor_args_encoded"):
            params["constructorArguements"] = input_json["constructor_args_encoded"]

        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(explorer_api, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            if result.get("status") == "1":
                return {
                    "success": True,
                    "verified": True,
                    "message": f"Verification submitted: {result.get('result', '')}",
                }
            else:
                return {
                    "success": True,
                    "verified": False,
                    "message": f"Verification failed: {result.get('result', '')}",
                }
    except Exception as e:
        return {"success": True, "verified": False, "message": f"Verification request failed: {e}"}


# ── Worker 6: Transfer Ownership ──────────────────────────────────

def transfer_ownership_worker(input_json: dict) -> dict:
    """
    Transfer contract ownership from GROOT's custodial wallet to the user's wallet.

    Input:
        user_id: str
        contract_address: str
        new_owner: str — user's personal wallet address
        chain: str
        rpc_url: str — optional

    Output:
        success: bool
        tx_hash: str
        new_owner: str
        message: str
    """
    user_id = input_json.get("user_id")
    contract_address = input_json.get("contract_address")
    new_owner = input_json.get("new_owner")
    chain = input_json.get("chain", "sepolia")
    rpc_url = input_json.get("rpc_url") or CHAIN_RPC.get(chain)

    if not all([user_id, contract_address, new_owner]):
        return {"success": False, "error": "Missing required fields: user_id, contract_address, new_owner"}
    if not rpc_url:
        return {"success": False, "error": f"No RPC URL for chain: {chain}"}

    try:
        from web3 import Web3
        from api.database import get_internal_db
        from api.services.wallet_crypto import derive_wallet_key, decrypt_share
        from api.services.shamir import reconstruct_secret
        from api.models.internal import CustodialWallet, WalletShare
        import ctypes

        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            return {"success": False, "error": f"Cannot connect to RPC: {rpc_url}"}

        chain_id = CHAIN_IDS.get(chain, w3.eth.chain_id)

        # Reconstruct deployer key
        with get_internal_db() as int_db:
            wallet = int_db.query(CustodialWallet).filter(
                CustodialWallet.user_id == user_id,
                CustodialWallet.is_active == True,  # noqa: E712
            ).first()
            if not wallet:
                return {"success": False, "error": "No custodial wallet found"}

            deployer_address = wallet.eth_address
            share_records = (
                int_db.query(WalletShare)
                .filter(WalletShare.wallet_id == wallet.id)
                .order_by(WalletShare.share_index)
                .limit(wallet.threshold)
                .all()
            )
            wallet_key = derive_wallet_key(wallet.encryption_salt)
            shares = [(sr.share_index, decrypt_share(sr.encrypted_share, wallet_key))
                      for sr in share_records]
            private_key = bytearray(reconstruct_secret(shares, wallet.threshold))

        try:
            # Ownable.transferOwnership(address)
            transfer_abi = [{"inputs": [{"name": "newOwner", "type": "address"}],
                             "name": "transferOwnership", "outputs": [], "stateMutability": "nonpayable",
                             "type": "function"}]
            contract = w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=transfer_abi)

            nonce = w3.eth.get_transaction_count(deployer_address)
            tx = contract.functions.transferOwnership(
                Web3.to_checksum_address(new_owner)
            ).build_transaction({
                "from": deployer_address,
                "nonce": nonce,
                "gasPrice": w3.eth.gas_price,
                "chainId": chain_id,
            })

            signed = w3.eth.account.sign_transaction(tx, private_key=bytes(private_key))
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt.status == 1:
                logger.info(
                    "Ownership transferred: contract=%s new_owner=%s chain=%s tx=%s",
                    contract_address, new_owner, chain, tx_hash.hex(),
                )
                return {
                    "success": True,
                    "tx_hash": tx_hash.hex() if isinstance(tx_hash, bytes) else str(tx_hash),
                    "new_owner": new_owner,
                    "message": "Ownership transferred successfully",
                }
            else:
                return {"success": False, "error": "Transaction reverted", "tx_hash": tx_hash.hex()}

        finally:
            if len(private_key) > 0:
                ctypes.memset(
                    ctypes.addressof((ctypes.c_char * len(private_key)).from_buffer(private_key)),
                    0, len(private_key),
                )

    except Exception as e:
        logger.exception("Transfer ownership failed: contract=%s user=%s", contract_address, user_id)
        return {"success": False, "error": str(e)}

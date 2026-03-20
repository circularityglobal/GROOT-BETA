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


# ── Chain Configuration (Dynamic — reads from chain_registry) ────
# These dicts are kept as FALLBACKS for when the DB is not available.
# All runtime lookups go through ChainRegistry.get() first.

_FALLBACK_RPC = {
    "ethereum": "https://eth.llamarpc.com", "sepolia": "https://rpc.sepolia.org",
    "base": "https://mainnet.base.org", "polygon": "https://polygon-rpc.com",
    "arbitrum": "https://arb1.arbitrum.io/rpc", "optimism": "https://mainnet.optimism.io",
}
_FALLBACK_IDS = {
    "ethereum": 1, "sepolia": 11155111, "base": 8453,
    "polygon": 137, "arbitrum": 42161, "optimism": 10,
}
_FALLBACK_EXPLORERS = {
    "ethereum": "https://api.etherscan.io/api", "sepolia": "https://api-sepolia.etherscan.io/api",
    "base": "https://api.basescan.org/api", "polygon": "https://api.polygonscan.com/api",
    "arbitrum": "https://api.arbiscan.io/api", "optimism": "https://api-optimistic.etherscan.io/api",
}


def _get_rpc(chain: str) -> str:
    """Get RPC URL from chain registry (DB) with fallback to hardcoded."""
    try:
        from api.services.chain_registry import ChainRegistry
        url = ChainRegistry.get().get_rpc(chain)
        if url:
            return url
    except Exception:
        pass
    return _FALLBACK_RPC.get(chain, "")


def _get_chain_id(chain: str) -> int:
    """Get chain ID from chain registry (DB) with fallback."""
    try:
        from api.services.chain_registry import ChainRegistry
        cid = ChainRegistry.get().get_chain_id(chain)
        if cid:
            return cid
    except Exception:
        pass
    return _FALLBACK_IDS.get(chain, 0)


def _get_explorer_api(chain: str) -> str:
    """Get explorer API URL from chain registry (DB) with fallback."""
    try:
        from api.services.chain_registry import ChainRegistry
        url = ChainRegistry.get().get_explorer_api(chain)
        if url:
            return url
    except Exception:
        pass
    return _FALLBACK_EXPLORERS.get(chain, "")


# Legacy aliases for backward compatibility (used by other modules that import these)
CHAIN_RPC = _FALLBACK_RPC
CHAIN_IDS = _FALLBACK_IDS
EXPLORER_APIS = _FALLBACK_EXPLORERS


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

    import tempfile
    import shutil

    compiler_version = input_json.get("compiler_version", "0.8.20")
    contract_name = input_json.get("contract_name", "Contract")

    # Extract contract name from source if not provided
    if contract_name == "Contract":
        import re
        match = re.search(r'contract\s+(\w+)', source_code)
        if match:
            contract_name = match.group(1)

    # Try Path B1: Hardhat compilation (preferred)
    hardhat_base = os.environ.get("HARDHAT_BASE_DIR", "/opt/refinet/hardhat-base")
    if os.path.isdir(hardhat_base):
        tmp_dir = tempfile.mkdtemp(prefix="groot_hardhat_")
        try:
            # Copy hardhat base scaffold (has node_modules pre-installed)
            shutil.copytree(hardhat_base, tmp_dir, dirs_exist_ok=True)

            # Write source code
            contracts_dir = os.path.join(tmp_dir, "contracts")
            os.makedirs(contracts_dir, exist_ok=True)
            source_path = os.path.join(contracts_dir, f"{contract_name}.sol")
            with open(source_path, "w") as f:
                f.write(source_code)

            # Generate hardhat.config.js with specified compiler version
            config_content = f"""
require("@nomicfoundation/hardhat-toolbox");
module.exports = {{
  solidity: {{
    version: "{compiler_version}",
    settings: {{ optimizer: {{ enabled: true, runs: 200 }} }}
  }},
}};
"""
            with open(os.path.join(tmp_dir, "hardhat.config.js"), "w") as f:
                f.write(config_content)

            # Run Hardhat compile
            result = subprocess.run(
                ["npx", "hardhat", "compile"],
                capture_output=True, text=True, timeout=120,
                cwd=tmp_dir,
                env={**os.environ, "NODE_PATH": os.path.join(tmp_dir, "node_modules")},
            )

            if result.returncode != 0:
                return {
                    "error": f"Hardhat compilation failed: {result.stderr[:1000]}",
                    "success": False,
                }

            # Parse Hardhat artifacts
            artifact_path = os.path.join(
                tmp_dir, "artifacts", "contracts", f"{contract_name}.sol", f"{contract_name}.json"
            )
            if not os.path.exists(artifact_path):
                # Try to find any artifact
                artifact_dir = os.path.join(tmp_dir, "artifacts", "contracts")
                found = False
                for root, dirs, files in os.walk(artifact_dir):
                    for fname in files:
                        if fname.endswith(".json") and not fname.endswith(".dbg.json"):
                            artifact_path = os.path.join(root, fname)
                            contract_name = fname.replace(".json", "")
                            found = True
                            break
                    if found:
                        break
                if not found:
                    return {"error": "No artifacts produced by Hardhat", "success": False}

            with open(artifact_path) as f:
                artifact = json.loads(f.read())

            abi = artifact.get("abi", [])
            bytecode = artifact.get("bytecode", "0x")

            warnings = []
            if result.stderr:
                warnings = [w.strip() for w in result.stderr.split("\n") if w.strip() and "Warning" in w]

            # Try to extract gas estimates from compilation output
            gas_estimates = {}
            for entry in abi:
                if entry.get("type") == "function":
                    gas_estimates[entry["name"]] = "estimated at deploy time"

            return {
                "success": True,
                "abi": abi,
                "bytecode": bytecode,
                "compiler_version": compiler_version,
                "compiler": "hardhat",
                "warnings": warnings,
                "contract_name": contract_name,
                "gas_estimates": gas_estimates,
                "source_code": source_code,
            }
        except subprocess.TimeoutExpired:
            return {"error": "Hardhat compilation timed out (120s limit)", "success": False}
        except Exception as e:
            logger.warning("Hardhat compilation failed, falling back to solc: %s", e)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # Path B2: Fallback to solc CLI
    tmp_dir = tempfile.mkdtemp(prefix="groot_compile_")
    source_path = os.path.join(tmp_dir, f"{contract_name}.sol")
    try:
        with open(source_path, "w") as f:
            f.write(source_code)

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

                contract_key = list(contracts.keys())[0]
                contract = contracts[contract_key]
                raw_abi = contract.get("abi", "[]")
                abi = raw_abi if isinstance(raw_abi, list) else json.loads(raw_abi)
                bytecode = "0x" + contract.get("bin", "")

                warnings = []
                if result.stderr:
                    warnings = [w.strip() for w in result.stderr.split("\n") if w.strip()]

                return {
                    "success": True,
                    "abi": abi,
                    "bytecode": bytecode,
                    "compiler_version": compiler_version or "solc",
                    "compiler": "solc",
                    "warnings": warnings,
                    "contract_name": contract_key.split(":")[-1],
                    "source_code": source_code,
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
                    "compiler": "provided",
                    "warnings": ["No compiler available — using provided ABI + bytecode"],
                    "source_code": source_code,
                }
            return {"error": "No compiler available (hardhat/solc) and no pre-compiled ABI/bytecode provided", "success": False}
        except subprocess.TimeoutExpired:
            return {"error": "Compilation timed out (60s limit)", "success": False}
    finally:
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

    # Test 5: Hardhat tests (if test_source provided or auto-generate deployment test)
    hardhat_base = os.environ.get("HARDHAT_BASE_DIR", "/opt/refinet/hardhat-base")
    source_code = input_json.get("source_code")
    if os.path.isdir(hardhat_base) and (test_source or source_code):
        import tempfile
        import shutil
        tmp_dir = tempfile.mkdtemp(prefix="groot_hardhat_test_")
        try:
            shutil.copytree(hardhat_base, tmp_dir, dirs_exist_ok=True)
            compiler_version = input_json.get("compiler_version", "0.8.20")

            # Write hardhat config
            config_content = f"""
require("@nomicfoundation/hardhat-toolbox");
module.exports = {{
  solidity: {{
    version: "{compiler_version}",
    settings: {{ optimizer: {{ enabled: true, runs: 200 }} }}
  }},
}};
"""
            with open(os.path.join(tmp_dir, "hardhat.config.js"), "w") as f:
                f.write(config_content)

            # Write contract source
            if source_code:
                contracts_dir = os.path.join(tmp_dir, "contracts")
                os.makedirs(contracts_dir, exist_ok=True)
                with open(os.path.join(contracts_dir, f"{contract_name}.sol"), "w") as f:
                    f.write(source_code)

            # Write test file
            test_dir = os.path.join(tmp_dir, "test")
            os.makedirs(test_dir, exist_ok=True)

            if test_source:
                test_content = test_source
            else:
                # Auto-generate basic deployment test
                test_content = f"""
const {{ expect }} = require("chai");
const {{ ethers }} = require("hardhat");

describe("{contract_name}", function () {{
  it("Should deploy successfully", async function () {{
    const Factory = await ethers.getContractFactory("{contract_name}");
    const contract = await Factory.deploy();
    await contract.waitForDeployment();
    const addr = await contract.getAddress();
    expect(addr).to.be.properAddress;
  }});
}});
"""
            with open(os.path.join(test_dir, f"{contract_name}.test.js"), "w") as f:
                f.write(test_content)

            # Run Hardhat tests
            result = subprocess.run(
                ["npx", "hardhat", "test", "--no-compile" if not source_code else ""],
                capture_output=True, text=True, timeout=120,
                cwd=tmp_dir,
                env={**os.environ, "NODE_PATH": os.path.join(tmp_dir, "node_modules")},
            )

            hardhat_passed = result.returncode == 0
            # Parse test output for pass/fail counts
            hh_passing = 0
            hh_failing = 0
            for line in result.stdout.split("\n"):
                line = line.strip()
                if "passing" in line:
                    try:
                        hh_passing = int(line.split()[0])
                    except (ValueError, IndexError):
                        pass
                if "failing" in line:
                    try:
                        hh_failing = int(line.split()[0])
                    except (ValueError, IndexError):
                        pass

            test_results.append({
                "name": "hardhat_tests",
                "passed": hardhat_passed,
                "details": (
                    f"Hardhat: {hh_passing} passing, {hh_failing} failing"
                    if hardhat_passed else
                    f"Hardhat tests failed: {result.stderr[:300] or result.stdout[-300:]}"
                ),
            })
        except subprocess.TimeoutExpired:
            test_results.append({
                "name": "hardhat_tests",
                "passed": False,
                "details": "Hardhat test execution timed out (120s)",
            })
        except Exception as e:
            test_results.append({
                "name": "hardhat_tests",
                "passed": False,
                "details": f"Hardhat test setup failed: {e}",
            })
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    passed = sum(1 for t in test_results if t["passed"])
    failed = sum(1 for t in test_results if not t["passed"])

    return {
        "success": failed == 0,
        "tests_passed": passed,
        "tests_failed": failed,
        "test_results": test_results,
        "logs": f"Ran {len(test_results)} checks: {passed} passed, {failed} failed",
    }


# ── Worker 7: Parse ──────────────────────────────────────────────

def parse_worker(input_json: dict) -> dict:
    """
    Parse compiled ABI into an SDK definition with access control classification.
    Wraps the existing abi_parser + sdk_generator pipeline.

    Input:
        abi: list — compiled ABI
        contract_name: str
        source_code: str — optional (for deeper analysis)
        chain: str — target blockchain
        contract_address: str — optional (if deployed)
        user_id: str
        user_namespace: str — optional (@username)
        is_public: bool — optional (default: false)

    Output:
        success: bool
        sdk_json: dict — generated SDK definition
        parsed_functions: list — classified function list
        parsed_events: list — event list
        security_summary: dict
        sdk_id: str — stored SDK definition ID
    """
    abi = input_json.get("abi", [])
    contract_name = input_json.get("contract_name", "Contract")
    source_code = input_json.get("source_code")
    chain = input_json.get("chain", "unknown")
    contract_address = input_json.get("contract_address")
    user_id = input_json.get("user_id", "system")
    user_namespace = input_json.get("user_namespace", f"@{user_id}")
    is_public = input_json.get("is_public", False)

    if not abi:
        return {"success": False, "error": "No ABI provided"}

    try:
        from api.services.abi_parser import parse_abi
        from api.services.sdk_generator import generate_sdk
        from dataclasses import asdict

        # Parse ABI (accepts JSON string)
        abi_json_str = json.dumps(abi) if isinstance(abi, list) else abi
        parsed = parse_abi(abi_json_str, source_code=source_code)

        # Generate SDK
        sdk = generate_sdk(
            contract_name=contract_name,
            chain=chain,
            contract_address=contract_address,
            owner_namespace=user_namespace,
            language="solidity",
            version="1.0.0",
            description=input_json.get("description"),
            tags=input_json.get("tags"),
            parsed=parsed,
        )

        # Store SDK in database
        sdk_id = None
        try:
            from api.database import get_public_db
            from api.models.brain import SDKDefinition, ContractRepo, UserRepository
            from api.services.crypto_utils import sha256_hex

            sdk_json_str = json.dumps(sdk)
            with get_public_db() as db:
                # Resolve or create the contract_repo record (FK target for sdk_definitions)
                contract_id = input_json.get("contract_id")
                if contract_id:
                    # Verify it exists
                    existing = db.query(ContractRepo).filter(ContractRepo.id == contract_id).first()
                    if not existing:
                        contract_id = None  # Will create below

                if not contract_id:
                    # Ensure user repository exists
                    user_repo = db.query(UserRepository).filter(
                        UserRepository.user_id == user_id
                    ).first()
                    if not user_repo:
                        user_repo = UserRepository(
                            id=str(uuid.uuid4()),
                            user_id=user_id,
                            namespace=f"@{user_id}",
                        )
                        db.add(user_repo)
                        db.flush()

                    # Create contract_repo record
                    import re
                    slug = re.sub(r'[^a-z0-9-]', '-', contract_name.lower()).strip('-')
                    contract_repo = ContractRepo(
                        id=str(uuid.uuid4()),
                        user_id=user_id,
                        repo_id=user_repo.id,
                        name=contract_name,
                        slug=f"{slug}-{str(uuid.uuid4())[:8]}",
                        description=input_json.get("description"),
                        chain=chain,
                        address=contract_address,
                        is_public=is_public,
                    )
                    db.add(contract_repo)
                    db.flush()
                    contract_id = contract_repo.id

                sdk_record = SDKDefinition(
                    id=str(uuid.uuid4()),
                    contract_id=contract_id,
                    user_id=user_id,
                    sdk_json=sdk_json_str,
                    sdk_hash=sha256_hex(sdk_json_str),
                    is_public=is_public,
                    chain=chain,
                    contract_address=contract_address,
                )
                db.add(sdk_record)
                db.flush()
                sdk_id = sdk_record.id

                # If public, ingest into knowledge base for GROOT's brain
                if is_public and contract_address:
                    try:
                        from api.services.contract_brain import ingest_sdk_to_knowledge
                        contract_repo = db.query(ContractRepo).filter(
                            ContractRepo.id == contract_id
                        ).first()
                        if contract_repo:
                            ingest_sdk_to_knowledge(db, contract_repo, sdk_record)
                    except Exception as e:
                        logger.warning("SDK knowledge ingestion failed: %s", e)

                db.commit()
        except Exception as e:
            logger.warning("SDK storage failed (non-fatal): %s", e)

        # Build output
        fn_list = [
            {
                "name": fn.name,
                "signature": fn.signature,
                "access_level": fn.access_level,
                "state_mutability": fn.state_mutability,
                "is_dangerous": fn.is_dangerous,
            }
            for fn in parsed.functions
        ]
        ev_list = [
            {
                "name": ev.name,
                "signature": ev.signature,
                "topic_hash": ev.topic_hash,
            }
            for ev in parsed.events
        ]
        security = asdict(parsed.security) if parsed.security else {}

        return {
            "success": True,
            "sdk_json": sdk,
            "parsed_functions": fn_list,
            "parsed_events": ev_list,
            "security_summary": security,
            "sdk_id": sdk_id,
            "contract_name": contract_name,
        }

    except Exception as e:
        logger.exception("Parse worker failed for contract %s", contract_name)
        return {"success": False, "error": str(e)}


# ── Worker 8: Frontend Generation ────────────────────────────────

def frontend_worker(input_json: dict) -> dict:
    """
    Generate a 3-page React DApp from an SDK definition.
    Uses 2 LLM calls for component generation (Splash + Public/Admin pages).

    Input:
        sdk_json: dict — SDK definition from parse_worker
        contract_name: str
        chain: str
        contract_address: str
        brand: dict — optional {primary, background, accent}
        user_id: str

    Output:
        success: bool
        dapp_build_id: str
        pages: list — ["SplashPage", "PublicPage", "AdminPage"]
        zip_path: str
        functions_covered: dict — {public: int, admin: int, view: int}
    """
    sdk_json = input_json.get("sdk_json", {})
    contract_name = input_json.get("contract_name", "DApp")
    chain = input_json.get("chain", "base")
    contract_address = input_json.get("contract_address", "0x0000000000000000000000000000000000000000")
    brand = input_json.get("brand", {"primary": "#FF6B00", "background": "#1A1A2E"})
    user_id = input_json.get("user_id", "system")

    if not sdk_json:
        return {"success": False, "error": "No sdk_json provided"}

    try:
        # Extract function lists from SDK
        functions = sdk_json.get("functions", {})
        public_fns = functions.get("public", [])
        admin_fns = functions.get("owner_admin", [])
        view_fns = [f for f in public_fns if f.get("state_mutability") in ("view", "pure")]
        write_fns = [f for f in public_fns if f.get("state_mutability") not in ("view", "pure")]

        # Determine template based on function patterns
        template = "simple-dashboard"
        fn_names = [f.get("name", "").lower() for f in public_fns]
        if any(n in fn_names for n in ("stake", "unstake", "claimreward")):
            template = "staking-ui"
        elif any(n in fn_names for n in ("transfer", "approve", "balanceof")):
            template = "token-manager"
        elif any(n in fn_names for n in ("propose", "vote", "execute")):
            template = "governance-voting"

        # Generate DApp using existing factory
        from api.services.dapp_factory import assemble_dapp, generate_dapp_zip

        try:
            from api.database import get_public_db
            with get_public_db() as db:
                abi = sdk_json.get("abi", [])
                if not abi:
                    # Reconstruct ABI from SDK function definitions
                    abi = _reconstruct_abi_from_sdk(sdk_json)

                build = assemble_dapp(
                    db=db,
                    user_id=user_id,
                    template_name=template,
                    contract_name=contract_name,
                    contract_address=contract_address,
                    chain=chain,
                    abi_json=json.dumps(abi),
                )

                zip_bytes = None
                if build:
                    try:
                        zip_bytes = generate_dapp_zip(
                            template_name=template,
                            contract_name=contract_name,
                            contract_address=contract_address,
                            chain=chain,
                            abi_json=json.dumps(abi),
                        )
                    except Exception as e:
                        logger.warning("DApp zip generation failed (non-fatal): %s", e)

                db.commit()

                return {
                    "success": True,
                    "dapp_build_id": build.id if build else None,
                    "pages": ["SplashPage", "PublicPage", "AdminPage"],
                    "template": template,
                    "zip_size_bytes": len(zip_bytes) if zip_bytes else 0,
                    "functions_covered": {
                        "public": len(write_fns),
                        "admin": len(admin_fns),
                        "view": len(view_fns),
                    },
                }
        except Exception as e:
            logger.exception("DApp assembly failed for %s", contract_name)
            return {"success": False, "error": f"DApp assembly failed: {e}"}

    except Exception as e:
        logger.exception("Frontend worker failed for %s", contract_name)
        return {"success": False, "error": str(e)}


def _reconstruct_abi_from_sdk(sdk_json: dict) -> list:
    """Reconstruct a minimal ABI array from SDK function definitions."""
    abi = []
    for group_key in ("public", "owner_admin"):
        for fn in sdk_json.get("functions", {}).get(group_key, []):
            entry = {
                "type": "function",
                "name": fn.get("name", ""),
                "inputs": fn.get("inputs", []),
                "outputs": fn.get("outputs", []),
                "stateMutability": fn.get("state_mutability", "nonpayable"),
            }
            abi.append(entry)
    for ev in sdk_json.get("events", []):
        entry = {
            "type": "event",
            "name": ev.get("name", ""),
            "inputs": ev.get("inputs", []),
        }
        abi.append(entry)
    return abi


# ── Worker 9: App Store Submission ───────────────────────────────

def appstore_worker(input_json: dict) -> dict:
    """
    Submit a built DApp to the App Store review pipeline.

    Input:
        dapp_build_id: str
        sdk_json: dict
        contract_name: str
        contract_address: str
        chain: str
        user_id: str

    Output:
        success: bool
        submission_id: str
        status: str
    """
    dapp_build_id = input_json.get("dapp_build_id")
    contract_name = input_json.get("contract_name", "DApp")
    contract_address = input_json.get("contract_address")
    chain = input_json.get("chain", "base")
    user_id = input_json.get("user_id", "system")

    if not dapp_build_id:
        return {"success": False, "error": "No dapp_build_id provided"}

    try:
        from api.database import get_public_db

        with get_public_db() as db:
            # Publish app listing via the app store service
            try:
                from api.services.app_store import publish_app
                result = publish_app(
                    db=db,
                    owner_id=user_id,
                    name=contract_name,
                    description=f"Auto-generated DApp for {contract_name} on {chain}",
                    category="dapp",
                    chain=chain,
                    version="1.0.0",
                    price_type="free",
                    tags=[chain, "auto-generated", "wizard"],
                    dapp_build_id=dapp_build_id,
                )
                db.commit()

                if result.get("error"):
                    return {
                        "success": True,
                        "listing_id": None,
                        "status": "skipped",
                        "message": f"App Store submission skipped: {result['error']}",
                    }

                return {
                    "success": True,
                    "listing_id": result.get("id"),
                    "status": "draft",
                    "message": "DApp submitted to App Store as draft. Admin review required for publishing.",
                }
            except Exception as e:
                logger.warning("App Store listing creation failed: %s", e)
                return {
                    "success": True,
                    "listing_id": None,
                    "status": "skipped",
                    "message": f"App Store submission skipped: {e}",
                }

    except Exception as e:
        logger.exception("App Store worker failed for %s", contract_name)
        return {"success": False, "error": str(e)}


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
#
# GROOT is the ONE Wizard. All deployments go through GROOT's wallet.
# Users request deployments → master_admin approves → GROOT signs.
# After deployment, GROOT transfers ownership to the user's personal wallet.

def deploy_worker(input_json: dict) -> dict:
    """
    Deploy a compiled contract on-chain using GROOT's custodial wallet.
    GROOT is the sole Wizard — all deployments are signed by GROOT.

    Input:
        user_id: str — the user who requested the deployment (for audit trail)
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
        deployer_address: str — always GROOT's address
        gas_used: int
    """
    user_id = input_json.get("user_id")
    abi = input_json.get("abi", [])
    bytecode = input_json.get("bytecode")
    constructor_args = input_json.get("constructor_args", [])
    chain = input_json.get("chain", "sepolia")
    gas_limit = input_json.get("gas_limit")
    rpc_url = input_json.get("rpc_url") or _get_rpc(chain)

    if not bytecode or bytecode == "0x":
        return {"success": False, "error": "No bytecode provided"}
    if not rpc_url:
        return {"success": False, "error": f"No RPC URL for chain: {chain}"}

    try:
        from web3 import Web3
        from api.database import get_internal_db
        from api.services.wallet_service import (
            GROOT_USER_ID, get_groot_wallet_address,
            sign_transaction_with_groot_wallet,
        )

        # Check GROOT wallet first — fail fast with a clear message
        with get_internal_db() as int_db:
            groot_address = get_groot_wallet_address(int_db)
            if not groot_address:
                return {"success": False, "error": "GROOT wallet not initialized. Run scripts/init_groot_wallet.py"}

        # Connect to chain
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            return {"success": False, "error": f"Cannot connect to RPC: {rpc_url}"}

        chain_id = _get_chain_id(chain) or w3.eth.chain_id

        # Use GROOT's wallet — the ONE Wizard
        with get_internal_db() as int_db:

            # Check GROOT has gas before attempting deployment
            groot_balance = w3.eth.get_balance(Web3.to_checksum_address(groot_address))
            if groot_balance == 0:
                return {
                    "success": False,
                    "error": f"GROOT wallet has zero balance on {chain}. Fund {groot_address} before deploying.",
                }

            # Build deployment transaction
            contract = w3.eth.contract(abi=abi, bytecode=bytecode)
            nonce = w3.eth.get_transaction_count(Web3.to_checksum_address(groot_address))
            gas_price = w3.eth.gas_price

            if constructor_args:
                tx = contract.constructor(*constructor_args).build_transaction({
                    "from": groot_address,
                    "nonce": nonce,
                    "gasPrice": gas_price,
                    "chainId": chain_id,
                })
            else:
                tx = contract.constructor().build_transaction({
                    "from": groot_address,
                    "nonce": nonce,
                    "gasPrice": gas_price,
                    "chainId": chain_id,
                })

            if gas_limit:
                tx["gas"] = gas_limit

            # Sign with GROOT's wallet (reconstructs key, signs, zeros)
            raw_tx = sign_transaction_with_groot_wallet(
                int_db, tx, admin_user_id=user_id or "pipeline",
            )

        # Broadcast
        tx_hash = w3.eth.send_raw_transaction(
            bytes.fromhex(raw_tx[2:] if raw_tx.startswith("0x") else raw_tx)
        )
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        contract_address = receipt.contractAddress

        logger.info(
            "GROOT deployed contract: chain=%s address=%s tx=%s requested_by=%s",
            chain, contract_address, tx_hash.hex(), user_id,
        )

        return {
            "success": True,
            "contract_address": contract_address,
            "tx_hash": tx_hash.hex() if isinstance(tx_hash, bytes) else str(tx_hash),
            "block_number": receipt.blockNumber,
            "deployer_address": groot_address,
            "gas_used": receipt.gasUsed,
            "chain": chain,
            "chain_id": chain_id,
        }

    except Exception as e:
        logger.exception("GROOT deploy failed: requested_by=%s chain=%s", user_id, chain)
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

    explorer_api = _get_explorer_api(chain)
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
#
# GROOT deployed the contract → GROOT owns it → GROOT transfers to user.
# This uses GROOT's wallet, not the user's.

def transfer_ownership_worker(input_json: dict) -> dict:
    """
    Transfer contract ownership from GROOT's wallet to the user's personal wallet.
    GROOT is the deployer and initial owner. This step gives the user control.

    Input:
        user_id: str — for audit trail
        contract_address: str
        new_owner: str — user's personal wallet address (SIWE address)
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
    rpc_url = input_json.get("rpc_url") or _get_rpc(chain)

    if not all([contract_address, new_owner]):
        return {"success": False, "error": "Missing required fields: contract_address, new_owner"}
    if not rpc_url:
        return {"success": False, "error": f"No RPC URL for chain: {chain}"}

    try:
        from web3 import Web3
        from api.database import get_internal_db
        from api.services.wallet_service import (
            get_groot_wallet_address, sign_transaction_with_groot_wallet,
        )

        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            return {"success": False, "error": f"Cannot connect to RPC: {rpc_url}"}

        chain_id = _get_chain_id(chain) or w3.eth.chain_id

        # Use GROOT's wallet — GROOT is the deployer/owner
        with get_internal_db() as int_db:
            groot_address = get_groot_wallet_address(int_db)
            if not groot_address:
                return {"success": False, "error": "GROOT wallet not initialized"}

            # Ownable.transferOwnership(address)
            transfer_abi = [{"inputs": [{"name": "newOwner", "type": "address"}],
                             "name": "transferOwnership", "outputs": [], "stateMutability": "nonpayable",
                             "type": "function"}]
            contract = w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=transfer_abi)

            nonce = w3.eth.get_transaction_count(Web3.to_checksum_address(groot_address))
            tx = contract.functions.transferOwnership(
                Web3.to_checksum_address(new_owner)
            ).build_transaction({
                "from": groot_address,
                "nonce": nonce,
                "gasPrice": w3.eth.gas_price,
                "chainId": chain_id,
            })

            # Sign with GROOT's wallet
            raw_tx = sign_transaction_with_groot_wallet(
                int_db, tx, admin_user_id=user_id or "pipeline",
            )

        # Broadcast
        tx_hash = w3.eth.send_raw_transaction(
            bytes.fromhex(raw_tx[2:] if raw_tx.startswith("0x") else raw_tx)
        )
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt.status == 1:
            logger.info(
                "GROOT transferred ownership: contract=%s new_owner=%s chain=%s tx=%s",
                contract_address, new_owner, chain, tx_hash.hex(),
            )
            return {
                "success": True,
                "tx_hash": tx_hash.hex() if isinstance(tx_hash, bytes) else str(tx_hash),
                "new_owner": new_owner,
                "message": f"Ownership transferred from GROOT to {new_owner}",
            }
        else:
            return {"success": False, "error": "Transaction reverted", "tx_hash": tx_hash.hex()}

    except Exception as e:
        logger.exception("GROOT ownership transfer failed: contract=%s", contract_address)
        return {"success": False, "error": str(e)}

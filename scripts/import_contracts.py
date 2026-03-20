#!/usr/bin/env python3
"""
GROOT Contract Import Script
Bulk-import contract JSON files into GROOT's brain (CAG).

Reads .json files from data/contracts/abis/, parses ABIs,
generates SDKs, and publishes to GROOT's knowledge base.

Usage:
    python3 scripts/import_contracts.py                    # Import all
    python3 scripts/import_contracts.py --chain ethereum    # Import one chain
    python3 scripts/import_contracts.py --file path/to.json # Import single file
    python3 scripts/import_contracts.py --fetch 0x... --chain ethereum  # Fetch from explorer
    python3 scripts/import_contracts.py --dry-run          # Preview only
"""

import argparse
import json
import os
import re
import sys
import uuid
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CONTRACTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "contracts", "abis")
ADMIN_USER_ID = "__admin__"

def _get_valid_chains():
    """Get valid chains from registry (DB) with fallback."""
    try:
        from api.services.chain_registry import ChainRegistry
        return ChainRegistry.get().get_chain_names()
    except Exception:
        return ["ethereum", "sepolia", "base", "polygon", "arbitrum", "optimism"]


def _get_explorer_api(chain):
    """Get explorer API URL from registry with fallback."""
    try:
        from api.services.chain_registry import ChainRegistry
        return ChainRegistry.get().get_explorer_api(chain)
    except Exception:
        fallback = {
            "ethereum": "https://api.etherscan.io/api", "sepolia": "https://api-sepolia.etherscan.io/api",
            "base": "https://api.basescan.org/api", "polygon": "https://api.polygonscan.com/api",
            "arbitrum": "https://api.arbiscan.io/api", "optimism": "https://api-optimistic.etherscan.io/api",
        }
        return fallback.get(chain)


def load_json_file(filepath: str) -> dict:
    """Load and validate a contract JSON file."""
    with open(filepath) as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object, got {type(data).__name__}")

    # Handle files that are just a raw ABI array
    if isinstance(data, list):
        return {"name": Path(filepath).stem, "abi": data}

    abi = data.get("abi")
    if not abi:
        raise ValueError("Missing 'abi' field")
    if not isinstance(abi, list):
        raise ValueError(f"'abi' must be an array, got {type(abi).__name__}")

    return data


def detect_chain_from_path(filepath: str) -> str:
    """Detect chain from directory structure: abis/ethereum/USDC.json -> ethereum"""
    parts = Path(filepath).parts
    for part in parts:
        if part in _get_valid_chains():
            return part
    return "ethereum"


def fetch_abi_from_explorer(address: str, chain: str) -> dict:
    """Fetch a verified ABI from a block explorer."""
    api_url = _get_explorer_api(chain)
    if not api_url:
        raise ValueError(f"Unsupported chain: {chain}")

    url = f"{api_url}?module=contract&action=getabi&address={address}"
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read())

    if data.get("status") != "1":
        raise ValueError(f"ABI not available: {data.get('result', 'unknown error')}")

    abi = json.loads(data["result"])

    # Try to guess contract name from functions
    name = address[:10] + "..."
    for entry in abi:
        if entry.get("type") == "function" and entry.get("name") in ("name", "symbol"):
            name = address  # Can't call on-chain from script, use address
            break

    return {
        "name": name,
        "chain": chain,
        "address": address,
        "abi": abi,
        "description": f"Contract at {address} on {chain}",
        "tags": [chain, "imported"],
    }


def import_contract(db, data: dict, chain_override: str = None, dry_run: bool = False) -> dict:
    """Import a single contract into the database. Supports multi-chain deployments."""
    from api.models.brain import UserRepository, ContractRepo, ContractFunction, ContractEvent, SDKDefinition
    from api.services.abi_parser import parse_abi
    from api.services.sdk_generator import generate_sdk
    from api.services.crypto_utils import sha256_hex

    name = data.get("name", "Unknown")
    # New format: deployments array (multi-chain)
    deployments = data.get("deployments", [])
    # Legacy format: single chain + address
    address = data.get("address")
    # For multi-chain format: use first deployment address as primary
    if not address and deployments:
        address = deployments[0].get("address")
    chain = chain_override or data.get("chain", "ethereum")
    description = data.get("description", "")
    tags = data.get("tags", [])
    abi = data["abi"]
    source_code = data.get("source_code")
    language = data.get("language", "solidity")

    # If no deployments array, build one from legacy chain+address
    if not deployments and address:
        try:
            from api.services.chain_registry import ChainRegistry
            chain_id = ChainRegistry.get().resolve_chain_id(chain)
        except Exception:
            chain_id = {"ethereum": 1, "base": 8453, "polygon": 137, "arbitrum": 42161, "optimism": 10, "sepolia": 11155111}.get(chain)
        if chain_id:
            deployments = [{"chain_id": chain_id, "address": address}]

    fn_count = sum(1 for e in abi if e.get("type") == "function")
    ev_count = sum(1 for e in abi if e.get("type") == "event")
    dep_count = len(deployments)

    if dry_run:
        return {"name": name, "chain": chain, "functions": fn_count, "events": ev_count, "deployments": dep_count, "status": "dry_run"}

    # Ensure admin user exists (FK target for user_repositories)
    from api.models.public import User
    admin_user = db.query(User).filter(User.id == ADMIN_USER_ID).first()
    if not admin_user:
        admin_user = User(
            id=ADMIN_USER_ID,
            email="admin@refinet.cloud",
            username="admin",
            tier="admin",
        )
        db.add(admin_user)
        db.flush()

    # Ensure admin user repository exists
    repo = db.query(UserRepository).filter(UserRepository.user_id == ADMIN_USER_ID).first()
    if not repo:
        repo = UserRepository(
            id=str(uuid.uuid4()),
            user_id=ADMIN_USER_ID,
            namespace="@admin",
        )
        db.add(repo)
        db.flush()

    # Check for duplicate (same name + chain + address)
    slug_base = re.sub(r'[^a-z0-9-]', '-', name.lower()).strip('-')
    existing = db.query(ContractRepo).filter(ContractRepo.slug.like(f"{slug_base}%")).first()
    if existing and existing.address == address:
        return {"name": name, "chain": chain, "status": "skipped", "reason": "already exists"}

    slug = f"{slug_base}-{uuid.uuid4().hex[:6]}"

    # Create contract record
    contract = ContractRepo(
        id=str(uuid.uuid4()),
        user_id=ADMIN_USER_ID,
        repo_id=repo.id,
        name=name,
        slug=slug,
        chain=chain,
        language=language,
        address=address,
        description=description,
        tags=json.dumps(tags) if tags else None,
        is_public=True,
        is_active=True,
    )
    db.add(contract)
    db.flush()

    # Parse ABI
    parsed = parse_abi(json.dumps(abi), source_code=source_code)

    # Store parsed functions
    for fn in parsed.functions:
        db.add(ContractFunction(
            id=str(uuid.uuid4()),
            contract_id=contract.id,
            function_name=fn.name,
            signature=fn.signature,
            selector=fn.selector,
            visibility=fn.visibility,
            state_mutability=fn.state_mutability,
            access_level=fn.access_level,
            access_modifier=fn.access_modifier,
            is_dangerous=fn.is_dangerous,
            danger_reason=fn.danger_reason,
            natspec_notice=fn.natspec_notice,
            is_sdk_enabled=True,
        ))

    # Store parsed events
    for ev in parsed.events:
        db.add(ContractEvent(
            id=str(uuid.uuid4()),
            contract_id=contract.id,
            event_name=ev.name,
            signature=ev.signature,
            topic_hash=ev.topic_hash,
        ))

    # Generate SDK
    sdk_data = generate_sdk(
        contract_name=name,
        chain=chain,
        contract_address=address,
        owner_namespace="@admin",
        language=language,
        version="1.0.0",
        description=description,
        tags=tags,
        parsed=parsed,
    )
    sdk_json_str = json.dumps(sdk_data)

    sdk = SDKDefinition(
        id=str(uuid.uuid4()),
        contract_id=contract.id,
        user_id=ADMIN_USER_ID,
        sdk_json=sdk_json_str,
        sdk_hash=sha256_hex(sdk_json_str),
        is_public=True,
        chain=chain,
        contract_address=address,
    )
    db.add(sdk)
    db.flush()

    # Ingest into knowledge base for GROOT RAG
    try:
        from api.services.contract_brain import ingest_sdk_to_knowledge
        ingest_sdk_to_knowledge(db, contract, sdk)
    except Exception as e:
        pass  # Non-fatal: SDK is still in registry

    # Store multi-chain deployments
    deployment_count = 0
    if deployments:
        try:
            from api.models.chain import ContractDeployment
            for dep in deployments:
                dep_chain_id = dep.get("chain_id")
                dep_address = dep.get("address")
                if not dep_chain_id or not dep_address:
                    continue
                # Skip if already exists
                existing_dep = db.query(ContractDeployment).filter(
                    ContractDeployment.chain_id == dep_chain_id,
                    ContractDeployment.address == dep_address,
                ).first()
                if existing_dep:
                    continue
                db.add(ContractDeployment(
                    id=str(uuid.uuid4()),
                    contract_id=contract.id,
                    chain_id=dep_chain_id,
                    address=dep_address,
                ))
                deployment_count += 1
            db.flush()
        except Exception as e:
            pass  # Non-fatal: legacy contracts don't need deployments table

    # Update contract status
    contract.status = "published"
    db.flush()

    return {
        "name": name,
        "chain": chain,
        "address": address,
        "functions": len(parsed.functions),
        "events": len(parsed.events),
        "sdk_id": sdk.id,
        "deployments": deployment_count,
        "status": "imported",
    }


def find_json_files(base_dir: str, chain_filter: str = None) -> list:
    """Find all .json files in the contracts directory."""
    files = []
    base = Path(base_dir)
    if not base.exists():
        return files

    for path in sorted(base.rglob("*.json")):
        if path.name == "manifest.json":
            continue
        if chain_filter:
            # Only include files under the chain subfolder
            if chain_filter not in str(path):
                continue
        files.append(str(path))
    return files


def main():
    parser = argparse.ArgumentParser(description="Import contract JSON files into GROOT's brain")
    parser.add_argument("--chain", type=str, help="Only import contracts for this chain")
    parser.add_argument("--file", type=str, help="Import a single JSON file")
    parser.add_argument("--fetch", type=str, help="Fetch ABI from block explorer (address)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to DB")
    parser.add_argument("--dir", type=str, default=CONTRACTS_DIR, help="Directory to scan for JSON files")
    args = parser.parse_args()

    print("=" * 60)
    print("  GROOT Contract Import")
    print("=" * 60)

    # Mode 1: Fetch from explorer and save to file
    if args.fetch:
        chain = args.chain or "ethereum"
        print(f"\nFetching ABI for {args.fetch} on {chain}...")
        try:
            data = fetch_abi_from_explorer(args.fetch, chain)
            # Save to file
            chain_dir = os.path.join(args.dir, chain)
            os.makedirs(chain_dir, exist_ok=True)
            filename = f"{data['name'].replace(' ', '_')}.json"
            filepath = os.path.join(chain_dir, filename)
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
            fn_count = sum(1 for e in data["abi"] if e.get("type") == "function")
            print(f"  Saved: {filepath}")
            print(f"  Functions: {fn_count}")
            print(f"\nNow run: python3 scripts/import_contracts.py --file {filepath}")
        except Exception as e:
            print(f"  FAILED: {e}")
            sys.exit(1)
        return

    # Mode 2: Import files
    if args.file:
        files = [args.file]
    else:
        files = find_json_files(args.dir, chain_filter=args.chain)

    if not files:
        print(f"\nNo .json files found in {args.dir}")
        if not args.chain:
            print(f"Create JSON files in: {args.dir}/")
            print(f"Or fetch from explorer: python3 scripts/import_contracts.py --fetch 0x... --chain ethereum")
        sys.exit(0)

    print(f"\nFound {len(files)} JSON file(s)")
    if args.dry_run:
        print("DRY RUN — no changes will be written\n")

    # Import
    import api.models  # noqa: Register models
    from api.database import init_databases, get_public_db
    init_databases()

    results = {"imported": 0, "skipped": 0, "failed": 0, "errors": []}

    with get_public_db() as db:
        for filepath in files:
            try:
                data = load_json_file(filepath)
                chain_from_path = detect_chain_from_path(filepath)
                chain = data.get("chain", chain_from_path)
                if args.chain:
                    chain = args.chain

                result = import_contract(db, data, chain_override=chain, dry_run=args.dry_run)

                status = result["status"]
                if status == "imported" or status == "dry_run":
                    results["imported"] += 1
                    icon = "[DRY]" if args.dry_run else "[OK]"
                elif status == "skipped":
                    results["skipped"] += 1
                    icon = "[SKIP]"
                else:
                    results["failed"] += 1
                    icon = "[FAIL]"

                print(f"  {icon} {result.get('name', '?'):30s} {chain:12s} {result.get('functions', 0):3d} fn  {result.get('events', 0):2d} ev  {result.get('address', '')[:14]}")

            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"{Path(filepath).name}: {str(e)[:80]}")
                print(f"  [ERR] {Path(filepath).name}: {str(e)[:100]}")
                try:
                    db.rollback()
                except Exception:
                    pass

        if not args.dry_run and results["imported"] > 0:
            db.commit()

    # Write manifest
    if not args.dry_run and results["imported"] > 0:
        manifest = {
            "last_import": datetime.now(timezone.utc).isoformat(),
            "imported": results["imported"],
            "skipped": results["skipped"],
            "failed": results["failed"],
        }
        manifest_path = os.path.join(os.path.dirname(args.dir), "manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"  Imported: {results['imported']} | Skipped: {results['skipped']} | Failed: {results['failed']}")
    if results["errors"]:
        print(f"  Errors:")
        for err in results["errors"][:5]:
            print(f"    - {err}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

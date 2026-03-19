"""
REFINET Cloud — Ownership Service
Track deployed contracts and manage ownership transfers.
"""

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from api.models.pipeline import DeploymentRecord, PendingAction

logger = logging.getLogger("refinet.ownership")


def get_user_deployments(
    db: Session,
    user_id: str,
    chain: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List all contracts deployed for a user."""
    query = db.query(DeploymentRecord).filter(DeploymentRecord.user_id == user_id)
    if chain:
        query = query.filter(DeploymentRecord.chain == chain)
    records = query.order_by(DeploymentRecord.created_at.desc()).offset(offset).limit(limit).all()
    return [_record_to_dict(r) for r in records]


def get_deployment(db: Session, deployment_id: str, user_id: Optional[str] = None) -> Optional[dict]:
    """Get a single deployment record."""
    query = db.query(DeploymentRecord).filter(DeploymentRecord.id == deployment_id)
    if user_id:
        query = query.filter(DeploymentRecord.user_id == user_id)
    record = query.first()
    return _record_to_dict(record) if record else None


def check_ownership_onchain(contract_address: str, chain: str, rpc_url: Optional[str] = None) -> dict:
    """Read the current owner() from an on-chain contract."""
    from api.services.wizard_workers import CHAIN_RPC

    rpc = rpc_url or CHAIN_RPC.get(chain)
    if not rpc:
        return {"error": f"No RPC URL for chain: {chain}"}

    try:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(rpc))
        if not w3.is_connected():
            return {"error": f"Cannot connect to RPC: {rpc}"}

        # Try Ownable.owner()
        owner_abi = [{"inputs": [], "name": "owner", "outputs": [{"name": "", "type": "address"}],
                      "stateMutability": "view", "type": "function"}]
        contract = w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=owner_abi)
        owner = contract.functions.owner().call()
        return {"owner": owner, "contract_address": contract_address, "chain": chain}
    except Exception as e:
        return {"error": f"Could not read owner(): {e}", "contract_address": contract_address}


def initiate_transfer(db: Session, deployment_id: str, target_address: str, user_id: str) -> dict:
    """
    Initiate ownership transfer for a deployed contract.
    Creates a PendingAction for admin approval.
    """
    record = db.query(DeploymentRecord).filter(
        DeploymentRecord.id == deployment_id,
        DeploymentRecord.user_id == user_id,
    ).first()
    if not record:
        return {"error": "Deployment not found"}
    if record.ownership_status != "groot_owned":
        return {"error": f"Contract is {record.ownership_status}, cannot transfer"}

    # Create pending action
    action = PendingAction(
        id=str(uuid.uuid4()),
        user_id=user_id,
        action_type="transfer_ownership",
        target_chain=record.chain,
        target_address=target_address,
        payload_json=json.dumps({
            "deployment_id": deployment_id,
            "contract_address": record.contract_address,
            "new_owner": target_address,
        }),
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
    )
    db.add(action)

    record.ownership_status = "transferring"
    db.flush()

    return {
        "pending_action_id": action.id,
        "deployment_id": deployment_id,
        "contract_address": record.contract_address,
        "new_owner": target_address,
        "message": "Transfer request submitted for admin approval",
    }


def _record_to_dict(r: DeploymentRecord) -> dict:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "pipeline_run_id": r.pipeline_run_id,
        "contract_address": r.contract_address,
        "chain": r.chain,
        "chain_id": r.chain_id,
        "deployer_address": r.deployer_address,
        "owner_address": r.owner_address,
        "tx_hash": r.tx_hash,
        "block_number": r.block_number,
        "ownership_status": r.ownership_status,
        "transfer_tx_hash": r.transfer_tx_hash,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "transferred_at": r.transferred_at.isoformat() if r.transferred_at else None,
    }

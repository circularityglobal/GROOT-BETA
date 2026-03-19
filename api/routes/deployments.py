"""
REFINET Cloud — Deployment Routes
Track and manage GROOT-deployed contracts and ownership transfers.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.database import public_db_dependency
from api.auth.jwt import decode_access_token
from api.auth.api_keys import validate_api_key
from api.services.ownership import (
    get_user_deployments, get_deployment, check_ownership_onchain, initiate_transfer,
)

router = APIRouter(prefix="/deployments", tags=["deployments"])


def _get_user_id(request: Request, db: Session) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = auth_header[7:]
    if token.startswith("rf_"):
        api_key = validate_api_key(db, token)
        if not api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return api_key.user_id
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload["sub"]


@router.get("/")
def list_deployments(
    request: Request,
    chain: str = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(public_db_dependency),
):
    """List user's deployed contracts."""
    user_id = _get_user_id(request, db)
    return get_user_deployments(db, user_id, chain=chain, limit=limit, offset=offset)


@router.get("/{deployment_id}")
def get_deployment_detail(
    deployment_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Get deployment details including ownership status."""
    user_id = _get_user_id(request, db)
    result = get_deployment(db, deployment_id, user_id=user_id)
    if not result:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return result


@router.post("/{deployment_id}/transfer")
def transfer_ownership(
    deployment_id: str,
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """
    Initiate ownership transfer to a target wallet address.
    Body: { target_address: "0x..." }
    """
    user_id = _get_user_id(request, db)
    target = body.get("target_address")
    if not target:
        raise HTTPException(status_code=400, detail="target_address is required")

    result = initiate_transfer(db, deployment_id, target, user_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    db.commit()
    return result


@router.get("/{deployment_id}/verify-owner")
def verify_owner_onchain(
    deployment_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Check the current on-chain owner of a deployed contract."""
    user_id = _get_user_id(request, db)
    deployment = get_deployment(db, deployment_id, user_id=user_id)
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    result = check_ownership_onchain(deployment["contract_address"], deployment["chain"])
    if "error" in result:
        raise HTTPException(status_code=502, detail=result["error"])
    return result

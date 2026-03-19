"""
REFINET Cloud — Chain Event Routes
Create watchers, list detected events, manage on-chain monitoring.
"""

import json
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.database import public_db_dependency
from api.auth.jwt import decode_access_token
from api.auth.api_keys import validate_api_key
from api.services.chain_listener import (
    create_watcher, list_watchers, delete_watcher, list_events,
)

router = APIRouter(prefix="/chain", tags=["chain"])


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


@router.post("/watchers")
def create_chain_watcher(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Create a new on-chain event watcher."""
    user_id = _get_user_id(request, db)

    chain = body.get("chain", "ethereum")
    address = body.get("contract_address")
    if not address:
        raise HTTPException(status_code=400, detail="contract_address is required")

    watcher = create_watcher(
        db=db,
        user_id=user_id,
        chain=chain,
        contract_address=address,
        event_names=body.get("event_names"),
        rpc_url=body.get("rpc_url"),
        from_block=body.get("from_block", 0),
        polling_interval=body.get("polling_interval_seconds", 30),
    )

    return {
        "id": watcher.id,
        "chain": watcher.chain,
        "contract_address": watcher.contract_address,
        "message": "Watcher created — events will be detected on next poll cycle",
    }


@router.get("/watchers")
def get_chain_watchers(
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """List all chain watchers for the authenticated user."""
    user_id = _get_user_id(request, db)
    return list_watchers(db, user_id)


@router.delete("/watchers/{watcher_id}")
def remove_chain_watcher(
    watcher_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Delete a chain watcher and its events."""
    user_id = _get_user_id(request, db)
    if not delete_watcher(db, watcher_id, user_id):
        raise HTTPException(status_code=404, detail="Watcher not found")
    return {"message": "Watcher deleted"}


@router.get("/watchers/{watcher_id}/events")
def get_chain_events(
    watcher_id: str,
    request: Request,
    limit: int = 50,
    db: Session = Depends(public_db_dependency),
):
    """List detected events for a specific watcher."""
    user_id = _get_user_id(request, db)

    # Verify ownership
    from api.models.public import ChainWatcher
    watcher = db.query(ChainWatcher).filter(
        ChainWatcher.id == watcher_id,
        ChainWatcher.user_id == user_id,
    ).first()
    if not watcher:
        raise HTTPException(status_code=404, detail="Watcher not found")

    return list_events(db, watcher_id, limit=limit)

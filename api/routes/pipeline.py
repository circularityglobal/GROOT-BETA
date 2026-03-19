"""
REFINET Cloud — Pipeline Routes
Create, monitor, and manage wizard worker pipelines (compile → test → deploy → transfer).
"""

import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.database import public_db_dependency
from api.auth.jwt import decode_access_token
from api.auth.api_keys import validate_api_key
from api.services.dag_orchestrator import (
    create_pipeline, run_pipeline, get_pipeline, list_pipelines,
    cancel_pipeline, list_pending_actions, approve_action, reject_action,
)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


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


def _require_admin(request: Request, db: Session) -> str:
    """Require admin role for an endpoint."""
    user_id = _get_user_id(request, db)
    from api.database import get_internal_db
    from api.models.internal import RoleAssignment
    with get_internal_db() as int_db:
        role = int_db.query(RoleAssignment).filter(
            RoleAssignment.user_id == user_id,
            RoleAssignment.role == "admin",
        ).first()
        if not role:
            raise HTTPException(status_code=403, detail="Admin access required")
    return user_id


# ── Pipeline CRUD ─────────────────────────────────────────────────

@router.post("/compile-test")
async def start_compile_test(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """
    Start a compile+test pipeline.
    Body: { source_code?, registry_project_id?, abi?, bytecode?, compiler_version? }
    """
    user_id = _get_user_id(request, db)
    pipeline = create_pipeline(db, user_id, "compile_test", body)
    db.commit()

    # Run async in background
    asyncio.create_task(_run_pipeline_background(pipeline.id))

    return {
        "pipeline_id": pipeline.id,
        "pipeline_type": "compile_test",
        "status": "pending",
        "message": "Pipeline started — poll GET /pipeline/{id} for status",
    }


@router.post("/deploy")
async def start_deploy_pipeline(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """
    Start a full deploy pipeline (compile → test → rbac → deploy → verify).
    Body: { source_code?, registry_project_id?, abi?, bytecode?, chain, constructor_args?, new_owner?, user_wallet_address? }
    For pipeline_type 'full', include new_owner or user_wallet_address to auto-transfer ownership.
    """
    user_id = _get_user_id(request, db)

    # Determine pipeline type: 'full' if transfer target provided, 'deploy' otherwise
    pipeline_type = "deploy"
    if body.get("new_owner") or body.get("user_wallet_address"):
        pipeline_type = "full"

    pipeline = create_pipeline(db, user_id, pipeline_type, body)
    db.commit()

    asyncio.create_task(_run_pipeline_background(pipeline.id))

    return {
        "pipeline_id": pipeline.id,
        "pipeline_type": pipeline_type,
        "status": "pending",
        "message": "Pipeline started — poll GET /pipeline/{id} for status",
    }


@router.get("/")
def get_pipelines(
    request: Request,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(public_db_dependency),
):
    """List user's pipelines."""
    user_id = _get_user_id(request, db)
    return list_pipelines(db, user_id, limit=limit, offset=offset)


@router.get("/{pipeline_id}")
def get_pipeline_detail(
    pipeline_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Get pipeline details with all steps."""
    user_id = _get_user_id(request, db)
    result = get_pipeline(db, pipeline_id, user_id=user_id)
    if not result:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return result


@router.post("/{pipeline_id}/cancel")
def cancel_pipeline_route(
    pipeline_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Cancel a running or pending pipeline."""
    user_id = _get_user_id(request, db)
    result = cancel_pipeline(db, pipeline_id, user_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    db.commit()
    return result


# ── Admin: Pending Actions ────────────────────────────────────────

@router.get("/admin/pending-actions")
def get_pending_actions(
    request: Request,
    status: str = "pending",
    limit: int = 50,
    db: Session = Depends(public_db_dependency),
):
    """List pending actions for admin review."""
    _require_admin(request, db)
    return list_pending_actions(db, status=status, limit=limit)


@router.post("/admin/pending-actions/{action_id}/approve")
async def approve_pending_action(
    action_id: str,
    request: Request,
    body: dict = None,
    db: Session = Depends(public_db_dependency),
):
    """Approve a pending action (may resume a paused pipeline)."""
    reviewer_id = _require_admin(request, db)
    note = (body or {}).get("note")
    result = await approve_action(db, action_id, reviewer_id, note)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    db.commit()
    return result


@router.post("/admin/pending-actions/{action_id}/reject")
async def reject_pending_action(
    action_id: str,
    request: Request,
    body: dict = None,
    db: Session = Depends(public_db_dependency),
):
    """Reject a pending action (will fail the linked pipeline)."""
    reviewer_id = _require_admin(request, db)
    note = (body or {}).get("note")
    result = await reject_action(db, action_id, reviewer_id, note)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    db.commit()
    return result


# ── Background Runner ─────────────────────────────────────────────

async def _run_pipeline_background(pipeline_id: str):
    """Run a pipeline in the background with its own DB session."""
    import logging
    logger = logging.getLogger("refinet.pipeline.bg")
    try:
        from api.database import get_public_db
        with get_public_db() as db:
            await run_pipeline(db, pipeline_id)
            db.commit()
    except Exception as e:
        logger.exception("Background pipeline failed: %s", pipeline_id)
        # Try to mark pipeline as failed
        try:
            from api.database import get_public_db
            from api.models.pipeline import PipelineRun
            from datetime import datetime, timezone
            with get_public_db() as db:
                p = db.query(PipelineRun).filter(PipelineRun.id == pipeline_id).first()
                if p and p.status not in ("completed", "failed", "cancelled"):
                    p.status = "failed"
                    p.error_message = f"Background execution error: {e}"
                    p.completed_at = datetime.now(timezone.utc)
                    db.commit()
        except Exception:
            pass

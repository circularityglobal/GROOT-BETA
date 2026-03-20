"""
REFINET Cloud — Worker Endpoints
Direct invocation of individual wizard workers for debugging and testing.

Auth tiers:
  Tier 1 (compile, test, parse, frontend): Any authenticated user
  Tier 2 (deploy, verify, rbac): Master admin only — these touch GROOT's wallet or authorization
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.database import public_db_dependency
from api.auth.jwt import decode_access_token
from api.auth.api_keys import validate_api_key

router = APIRouter(prefix="/workers", tags=["workers"])


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


def _require_master_admin(request: Request, db: Session) -> str:
    """Tier 2 worker endpoints require master_admin — they touch GROOT's wallet or authorization."""
    user_id = _get_user_id(request, db)
    from api.database import get_internal_db
    from api.auth.roles import is_master_admin
    with get_internal_db() as int_db:
        if not is_master_admin(int_db, user_id):
            raise HTTPException(
                status_code=403,
                detail="Master admin role required for Tier 2 worker operations."
            )
    return user_id


@router.post("/hardhat/compile")
def worker_compile(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """
    Compile a Solidity contract via Hardhat (or solc fallback).
    Body: { source_code, compiler_version?, contract_name?, registry_project_id?, abi?, bytecode? }
    """
    _get_user_id(request, db)
    from api.services.wizard_workers import compile_worker
    return compile_worker(body)


@router.post("/hardhat/test")
def worker_test(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """
    Run contract tests (static analysis + optional Hardhat tests).
    Body: { abi, bytecode, contract_name?, test_source?, source_code?, compiler_version? }
    """
    _get_user_id(request, db)
    from api.services.wizard_workers import test_worker
    return test_worker(body)


@router.post("/parse")
def worker_parse(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """
    Parse ABI into SDK definition with access control classification.
    Body: { abi, contract_name, chain?, contract_address?, source_code?, is_public? }
    """
    user_id = _get_user_id(request, db)
    body["user_id"] = user_id
    from api.services.wizard_workers import parse_worker
    return parse_worker(body)


@router.post("/rbac/check")
def worker_rbac(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """
    Check RBAC permissions for a Tier 2 action. Master admin only.
    Body: { action_type, target_chain, target_address? }
    """
    user_id = _require_master_admin(request, db)
    body["user_id"] = user_id
    from api.services.wizard_workers import rbac_check_worker
    return rbac_check_worker(body, db=db)


@router.post("/deploy")
def worker_deploy(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """
    Deploy a compiled contract on-chain. Master admin only.
    Body: { abi, bytecode, chain, constructor_args?, gas_limit? }
    """
    user_id = _require_master_admin(request, db)
    body["user_id"] = user_id
    from api.services.wizard_workers import deploy_worker
    return deploy_worker(body)


@router.post("/verify")
def worker_verify(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """
    Verify contract source on block explorer. Master admin only.
    Body: { contract_address, chain, source_code?, compiler_version? }
    """
    _require_master_admin(request, db)
    from api.services.wizard_workers import verify_worker
    return verify_worker(body)


@router.post("/frontend/generate")
def worker_frontend(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """
    Generate a 3-page React DApp from an SDK definition.
    Body: { sdk_json, contract_name, chain, contract_address?, brand? }
    """
    user_id = _get_user_id(request, db)
    body["user_id"] = user_id
    from api.services.wizard_workers import frontend_worker
    return frontend_worker(body)

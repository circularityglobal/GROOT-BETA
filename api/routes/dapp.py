"""
REFINET Cloud — DApp Factory Routes
Template browsing, DApp assembly, and download.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from api.database import public_db_dependency
from api.auth.jwt import decode_access_token
from api.auth.api_keys import validate_api_key
from api.services.dapp_factory import list_templates, assemble_dapp, generate_dapp_zip
from api.models.public import DAppBuild

router = APIRouter(prefix="/dapp", tags=["dapp"])


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


@router.get("/templates")
def get_templates():
    """List available DApp templates."""
    return list_templates()


@router.post("/build")
def build_dapp(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Assemble a DApp from a template and contract configuration."""
    user_id = _get_user_id(request, db)

    template = body.get("template_name")
    contract_name = body.get("contract_name")
    contract_address = body.get("contract_address")
    chain = body.get("chain", "ethereum")

    if not template or not contract_name or not contract_address:
        raise HTTPException(
            status_code=400,
            detail="template_name, contract_name, and contract_address are required",
        )

    build = assemble_dapp(
        db=db,
        user_id=user_id,
        template_name=template,
        contract_name=contract_name,
        contract_address=contract_address,
        chain=chain,
        abi_json=body.get("abi_json"),
        project_id=body.get("project_id"),
    )
    db.commit()

    return {
        "build_id": build.id,
        "status": build.status,
        "template": template,
        "output_filename": build.output_filename,
        "error": build.error_message,
    }


@router.get("/builds")
def list_builds(
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """List user's DApp builds."""
    user_id = _get_user_id(request, db)

    builds = db.query(DAppBuild).filter(
        DAppBuild.user_id == user_id,
    ).order_by(DAppBuild.created_at.desc()).limit(20).all()

    return [
        {
            "id": b.id,
            "template_name": b.template_name,
            "status": b.status,
            "output_filename": b.output_filename,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in builds
    ]


@router.get("/builds/{build_id}/download")
def download_dapp(
    build_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Download a built DApp as a zip file."""
    user_id = _get_user_id(request, db)

    build = db.query(DAppBuild).filter(
        DAppBuild.id == build_id,
        DAppBuild.user_id == user_id,
    ).first()

    if not build:
        raise HTTPException(status_code=404, detail="Build not found")
    if build.status != "ready":
        raise HTTPException(status_code=400, detail=f"Build not ready (status: {build.status})")

    config = json.loads(build.config_json) if build.config_json else {}

    zip_bytes = generate_dapp_zip(
        template_name=build.template_name,
        contract_name=config.get("contract_name", "Contract"),
        contract_address=config.get("contract_address", "0x"),
        chain=config.get("chain", "ethereum"),
    )

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{build.output_filename}"',
        },
    )


@router.get("/builds/{build_id}/validation")
def get_validation_status(
    build_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Get validation status for a DApp build."""
    user_id = _get_user_id(request, db)
    build = db.query(DAppBuild).filter(
        DAppBuild.id == build_id,
        DAppBuild.user_id == user_id,
    ).first()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")

    return {
        "build_id": build.id,
        "validation_status": build.validation_status,
        "validation_errors": json.loads(build.validation_errors) if build.validation_errors else None,
    }


@router.post("/builds/{build_id}/validate")
def validate_build(
    build_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Run validation on a DApp build (npm install + tsc check)."""
    user_id = _get_user_id(request, db)
    build = db.query(DAppBuild).filter(
        DAppBuild.id == build_id,
        DAppBuild.user_id == user_id,
    ).first()
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")
    if build.status != "ready":
        raise HTTPException(status_code=400, detail=f"Build not ready (status: {build.status})")

    from api.services.dapp_validator import validate_dapp
    result = validate_dapp(db, build_id)
    db.commit()
    return result

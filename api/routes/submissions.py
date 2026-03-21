"""
REFINET Cloud — App Submission Routes
Developer-facing routes for submitting apps for review.

CIFI Federation gate: All submission actions (create, upload, submit)
require a verified CIFI identity (@username). This ensures every app
in the store is linked to a KYC-verifiable identity.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from sqlalchemy.orm import Session

from api.database import public_db_dependency
from api.auth.jwt import decode_access_token
from api.auth.api_keys import validate_api_key
from api.services.submission import (
    create_submission, submit_for_review, upload_artifact,
    list_user_submissions, get_submission_detail, withdraw_submission,
    add_review_note,
)

router = APIRouter(prefix="/apps/submissions", tags=["submissions"])


def _get_user_id(request: Request, db: Session) -> str:
    """Extract user_id from JWT or API key."""
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


def _require_cifi_verified(db: Session, user_id: str) -> None:
    """
    Enforce CIFI federation identity for app store submissions.
    Users must have a verified @username from CIFI.GLOBAL to submit,
    upload artifacts, or request review for apps in the store.
    """
    from api.models.public import User

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not getattr(user, "cifi_verified", False) or not getattr(user, "cifi_username", None):
        raise HTTPException(
            status_code=403,
            detail=(
                "CIFI identity verification required. "
                "You must have a verified @username from CIFI.GLOBAL to submit apps to the store. "
                "Go to Settings or the Onboarding Wizard to verify your identity."
            ),
        )


# ── Create Submission ─────────────────────────────────────────────

@router.post("")
def create_submission_route(
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Create a new submission for App Store review. Requires CIFI identity."""
    user_id = _get_user_id(request, db)
    _require_cifi_verified(db, user_id)

    name = body.get("name")
    category = body.get("category")
    if not name or not category:
        raise HTTPException(status_code=400, detail="'name' and 'category' are required")

    result = create_submission(
        db,
        submitter_id=user_id,
        name=name,
        category=category,
        description=body.get("description", ""),
        readme=body.get("readme"),
        chain=body.get("chain"),
        version=body.get("version", "1.0.0"),
        icon_url=body.get("icon_url"),
        screenshots=body.get("screenshots"),
        tags=body.get("tags"),
        price_type=body.get("price_type", "free"),
        price_amount=float(body.get("price_amount", 0)),
        price_token=body.get("price_token"),
        license_type=body.get("license_type", "open"),
        external_url=body.get("external_url"),
        app_listing_id=body.get("app_listing_id"),
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Upload Artifact ───────────────────────────────────────────────

@router.post("/{submission_id}/artifact")
async def upload_artifact_route(
    submission_id: str,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(public_db_dependency),
):
    """Upload a ZIP artifact for a submission. Requires CIFI identity."""
    user_id = _get_user_id(request, db)
    _require_cifi_verified(db, user_id)

    data = await file.read()
    result = upload_artifact(
        db,
        submission_id=submission_id,
        submitter_id=user_id,
        artifact_bytes=data,
        artifact_filename=file.filename or "artifact.zip",
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Submit for Review ─────────────────────────────────────────────

@router.post("/{submission_id}/submit")
def submit_for_review_route(
    submission_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Submit a draft for review. Triggers automated scan. Requires CIFI identity."""
    user_id = _get_user_id(request, db)
    _require_cifi_verified(db, user_id)

    result = submit_for_review(db, submission_id, user_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── List My Submissions ───────────────────────────────────────────

@router.get("")
def list_my_submissions_route(
    request: Request,
    status: str = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(public_db_dependency),
):
    """List my submissions."""
    user_id = _get_user_id(request, db)
    return list_user_submissions(db, user_id, status=status, page=page, page_size=page_size)


# ── Get Submission Detail ─────────────────────────────────────────

@router.get("/{submission_id}")
def get_submission_detail_route(
    submission_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Get full submission detail with notes."""
    user_id = _get_user_id(request, db)

    result = get_submission_detail(db, submission_id, user_id)
    if not result:
        raise HTTPException(status_code=404, detail="Submission not found")
    return result


# ── Add Note (developer can comment on their own submission) ──────

@router.post("/{submission_id}/notes")
def add_note_route(
    submission_id: str,
    body: dict,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Add a comment to a submission."""
    user_id = _get_user_id(request, db)

    content = body.get("content")
    if not content:
        raise HTTPException(status_code=400, detail="'content' is required")

    # Verify the user owns this submission
    from api.models.public import AppSubmission
    sub = db.query(AppSubmission).filter(
        AppSubmission.id == submission_id,
        AppSubmission.submitter_id == user_id,
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    result = add_review_note(db, submission_id, user_id, content, "comment")
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Withdraw ──────────────────────────────────────────────────────

@router.delete("/{submission_id}")
def withdraw_submission_route(
    submission_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Withdraw a submission."""
    user_id = _get_user_id(request, db)

    result = withdraw_submission(db, submission_id, user_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Download artifact (for approved apps) ─────────────────────────

@router.get("/{submission_id}/download")
def download_artifact_route(
    submission_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Download the artifact of an approved submission. Requires authentication."""
    # Require auth to prevent enumeration / unauthorized download
    _get_user_id(request, db)

    from api.models.public import AppSubmission
    sub = db.query(AppSubmission).filter(AppSubmission.id == submission_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    if sub.status not in ("approved", "published"):
        raise HTTPException(status_code=403, detail="Artifact only available for approved submissions")

    import os
    if not sub.artifact_path or not os.path.exists(sub.artifact_path):
        raise HTTPException(status_code=404, detail="Artifact file not found")

    # Path traversal guard — ensure artifact_path is within submissions dir
    real_path = os.path.realpath(sub.artifact_path)
    submissions_base = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "submissions"))
    if not real_path.startswith(submissions_base):
        raise HTTPException(status_code=403, detail="Access denied")

    from fastapi.responses import FileResponse
    return FileResponse(
        real_path,
        media_type="application/zip",
        filename=sub.artifact_filename or "artifact.zip",
    )

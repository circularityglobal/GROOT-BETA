"""
REFINET Cloud — App Submission & Review Service
Apple/Google-style submission pipeline: submit → scan → sandbox → review → approve/reject → publish.
"""

import hashlib
import json
import logging
import os
import re
import shutil
import zipfile
from datetime import datetime, timezone, timedelta
from io import BytesIO
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import desc

from api.models.public import AppSubmission, SubmissionNote, AppListing, User

logger = logging.getLogger("refinet.submission")

VALID_CATEGORIES = ("dapp", "agent", "tool", "template", "dataset", "api-service", "digital-asset")
VALID_STATUSES = ("draft", "submitted", "automated_review", "in_review", "changes_requested", "approved", "rejected", "published")
SUBMISSIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "submissions")

# Max artifact size: 100MB
MAX_ARTIFACT_SIZE = 100 * 1024 * 1024

# Dangerous patterns for automated scan
DANGEROUS_PATTERNS = [
    (r"subprocess\.(call|run|Popen)", "subprocess execution"),
    (r"os\.system\(", "os.system call"),
    (r"eval\(", "eval() usage"),
    (r"exec\(", "exec() usage"),
    (r"__import__\(", "dynamic import"),
    (r"open\(.*/etc/", "sensitive file access"),
    (r"rm\s+-rf", "destructive shell command"),
    (r"DROP\s+TABLE", "SQL drop table"),
    (r"private[_\s]?key", "possible private key exposure"),
    (r"BEGIN\s+(RSA|EC|OPENSSH)\s+PRIVATE\s+KEY", "private key literal"),
]


def _submission_to_dict(sub: AppSubmission, author_username: Optional[str] = None) -> dict:
    """Serialize an AppSubmission."""
    return {
        "id": sub.id,
        "submitter_id": sub.submitter_id,
        "submitter_username": author_username,
        "app_listing_id": sub.app_listing_id,
        "name": sub.name,
        "description": sub.description,
        "category": sub.category,
        "chain": sub.chain,
        "version": sub.version,
        "icon_url": sub.icon_url,
        "screenshots": json.loads(sub.screenshots) if sub.screenshots else [],
        "tags": json.loads(sub.tags) if sub.tags else [],
        "price_type": sub.price_type or "free",
        "price_amount": sub.price_amount or 0.0,
        "price_token": sub.price_token,
        "license_type": sub.license_type or "open",
        "external_url": sub.external_url,
        "submission_type": sub.submission_type,
        "artifact_filename": sub.artifact_filename,
        "artifact_hash": sub.artifact_hash,
        "artifact_size_bytes": sub.artifact_size_bytes,
        "status": sub.status,
        "reviewer_id": sub.reviewer_id,
        "review_started_at": sub.review_started_at.isoformat() if sub.review_started_at else None,
        "review_completed_at": sub.review_completed_at.isoformat() if sub.review_completed_at else None,
        "rejection_reason": sub.rejection_reason,
        "automated_scan_status": sub.automated_scan_status,
        "automated_scan_result": json.loads(sub.automated_scan_result) if sub.automated_scan_result else None,
        "sandbox_id": sub.sandbox_id,
        "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
        "updated_at": sub.updated_at.isoformat() if sub.updated_at else None,
    }


def _note_to_dict(note: SubmissionNote, author_username: Optional[str] = None) -> dict:
    return {
        "id": note.id,
        "submission_id": note.submission_id,
        "author_id": note.author_id,
        "author_username": author_username,
        "note_type": note.note_type,
        "content": note.content,
        "created_at": note.created_at.isoformat() if note.created_at else None,
    }


# ══════════════════════════════════════════════════════════════════
# DEVELOPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def create_submission(
    db: Session,
    submitter_id: str,
    name: str,
    category: str,
    description: str = "",
    readme: Optional[str] = None,
    chain: Optional[str] = None,
    version: str = "1.0.0",
    icon_url: Optional[str] = None,
    screenshots: Optional[list[str]] = None,
    tags: Optional[list[str]] = None,
    price_type: str = "free",
    price_amount: float = 0.0,
    price_token: Optional[str] = None,
    license_type: str = "open",
    external_url: Optional[str] = None,
    app_listing_id: Optional[str] = None,
    artifact_bytes: Optional[bytes] = None,
    artifact_filename: Optional[str] = None,
) -> dict:
    """Create a new submission for App Store review."""
    if category not in VALID_CATEGORIES:
        return {"error": f"category must be one of: {', '.join(VALID_CATEGORIES)}"}

    user = db.query(User).filter(User.id == submitter_id).first()
    if not user:
        return {"error": "User not found"}

    # Determine submission type
    submission_type = "new"
    if app_listing_id:
        existing = db.query(AppListing).filter(AppListing.id == app_listing_id).first()
        if existing and existing.owner_id == submitter_id:
            submission_type = "update"
        elif existing:
            return {"error": "You can only submit updates to your own apps"}

    sub = AppSubmission(
        submitter_id=submitter_id,
        app_listing_id=app_listing_id,
        name=name,
        description=description,
        readme=readme,
        category=category,
        chain=chain,
        version=version,
        icon_url=icon_url,
        screenshots=json.dumps(screenshots) if screenshots else None,
        tags=json.dumps(tags) if tags else None,
        price_type=price_type,
        price_amount=price_amount,
        price_token=price_token,
        license_type=license_type,
        external_url=external_url,
        submission_type=submission_type,
        status="draft",
    )
    db.add(sub)
    db.flush()

    # Store artifact if provided
    if artifact_bytes:
        result = _store_artifact(sub, artifact_bytes, artifact_filename)
        if "error" in result:
            # Rollback the submission record since artifact failed
            db.expunge(sub)
            db.rollback()
            return result
        db.flush()

    return _submission_to_dict(sub, user.username)


def _store_artifact(sub: AppSubmission, data: bytes, filename: Optional[str] = None) -> dict:
    """Store uploaded artifact and compute hash."""
    if len(data) > MAX_ARTIFACT_SIZE:
        return {"error": f"Artifact too large. Maximum size is {MAX_ARTIFACT_SIZE // (1024*1024)}MB"}

    # Validate it's a valid zip + check for zip bomb
    MAX_EXTRACTED_SIZE = 500 * 1024 * 1024  # 500MB decompressed limit
    try:
        zf = zipfile.ZipFile(BytesIO(data))
        zf.testzip()
        total_extracted = sum(info.file_size for info in zf.infolist() if not info.is_dir())
        zf.close()
        if total_extracted > MAX_EXTRACTED_SIZE:
            return {"error": f"Archive decompresses to {total_extracted // (1024*1024)}MB — exceeds {MAX_EXTRACTED_SIZE // (1024*1024)}MB limit (possible zip bomb)"}
    except zipfile.BadZipFile:
        return {"error": "Artifact must be a valid ZIP file"}
    except Exception:
        return {"error": "Failed to validate ZIP file"}

    # Create storage directory
    sub_dir = os.path.join(SUBMISSIONS_DIR, sub.id)
    os.makedirs(sub_dir, exist_ok=True)

    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", filename or "artifact.zip")
    artifact_path = os.path.join(sub_dir, safe_name)

    with open(artifact_path, "wb") as f:
        f.write(data)

    sub.artifact_filename = safe_name
    sub.artifact_path = artifact_path
    sub.artifact_hash = hashlib.sha256(data).hexdigest()
    sub.artifact_size_bytes = len(data)

    return {"stored": True}


def submit_for_review(db: Session, submission_id: str, submitter_id: str) -> dict:
    """Move submission from draft to submitted. Triggers automated scan."""
    sub = db.query(AppSubmission).filter(
        AppSubmission.id == submission_id,
        AppSubmission.submitter_id == submitter_id,
    ).first()
    if not sub:
        return {"error": "Submission not found"}

    if sub.status not in ("draft", "changes_requested"):
        return {"error": f"Cannot submit from status '{sub.status}'. Must be 'draft' or 'changes_requested'"}

    if not sub.artifact_path or not os.path.exists(sub.artifact_path):
        return {"error": "No artifact uploaded. Upload a ZIP file before submitting"}

    sub.status = "submitted"
    sub.submitted_at = datetime.now(timezone.utc)
    sub.updated_at = datetime.now(timezone.utc)
    if sub.submission_type == "resubmission":
        pass  # keep as resubmission
    elif sub.status == "changes_requested":
        sub.submission_type = "resubmission"
    db.flush()

    # Run automated scan
    scan_result = run_automated_scan(db, submission_id)
    return {
        "message": "Submission sent for review",
        "submission_id": sub.id,
        "status": sub.status,
        "automated_scan": scan_result.get("scan_status"),
    }


def upload_artifact(
    db: Session,
    submission_id: str,
    submitter_id: str,
    artifact_bytes: bytes,
    artifact_filename: str,
) -> dict:
    """Upload or replace the artifact for a submission."""
    sub = db.query(AppSubmission).filter(
        AppSubmission.id == submission_id,
        AppSubmission.submitter_id == submitter_id,
    ).first()
    if not sub:
        return {"error": "Submission not found"}

    if sub.status not in ("draft", "changes_requested"):
        return {"error": f"Cannot upload artifact in status '{sub.status}'"}

    result = _store_artifact(sub, artifact_bytes, artifact_filename)
    if "error" in result:
        return result

    sub.updated_at = datetime.now(timezone.utc)
    db.flush()

    return {
        "message": "Artifact uploaded",
        "filename": sub.artifact_filename,
        "hash": sub.artifact_hash,
        "size_bytes": sub.artifact_size_bytes,
    }


def list_user_submissions(
    db: Session,
    user_id: str,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """List submissions by a user."""
    q = db.query(AppSubmission).filter(AppSubmission.submitter_id == user_id)
    if status:
        q = q.filter(AppSubmission.status == status)

    total = q.count()
    offset = (page - 1) * page_size
    subs = q.order_by(desc(AppSubmission.created_at)).offset(offset).limit(page_size).all()

    user = db.query(User).filter(User.id == user_id).first()
    username = user.username if user else None

    return {
        "submissions": [_submission_to_dict(s, username) for s in subs],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_submission_detail(db: Session, submission_id: str, user_id: Optional[str] = None) -> Optional[dict]:
    """Get full submission detail with notes. If user_id is set, verify ownership."""
    sub = db.query(AppSubmission).filter(AppSubmission.id == submission_id).first()
    if not sub:
        return None

    if user_id and sub.submitter_id != user_id:
        return None

    user = db.query(User).filter(User.id == sub.submitter_id).first()
    result = _submission_to_dict(sub, user.username if user else None)
    result["readme"] = sub.readme

    # Fetch notes
    notes = db.query(SubmissionNote).filter(
        SubmissionNote.submission_id == submission_id,
    ).order_by(SubmissionNote.created_at).all()

    author_ids = list({n.author_id for n in notes})
    authors = {u.id: u.username for u in db.query(User).filter(User.id.in_(author_ids)).all()} if author_ids else {}

    result["notes"] = [_note_to_dict(n, authors.get(n.author_id)) for n in notes]
    return result


def withdraw_submission(db: Session, submission_id: str, submitter_id: str) -> dict:
    """Withdraw a submission (developer cancels)."""
    sub = db.query(AppSubmission).filter(
        AppSubmission.id == submission_id,
        AppSubmission.submitter_id == submitter_id,
    ).first()
    if not sub:
        return {"error": "Submission not found"}

    if sub.status in ("approved", "published"):
        return {"error": "Cannot withdraw an approved or published submission"}

    # Clean up artifact
    if sub.artifact_path and os.path.exists(os.path.dirname(sub.artifact_path)):
        shutil.rmtree(os.path.dirname(sub.artifact_path), ignore_errors=True)

    db.delete(sub)
    db.flush()
    return {"message": "Submission withdrawn"}


# ══════════════════════════════════════════════════════════════════
# AUTOMATED SCANNING
# ══════════════════════════════════════════════════════════════════

def run_automated_scan(db: Session, submission_id: str) -> dict:
    """Run basic static analysis on the uploaded artifact."""
    sub = db.query(AppSubmission).filter(AppSubmission.id == submission_id).first()
    if not sub:
        return {"error": "Submission not found"}

    if not sub.artifact_path or not os.path.exists(sub.artifact_path):
        sub.automated_scan_status = "skipped"
        sub.automated_scan_result = json.dumps({"reason": "No artifact to scan"})
        db.flush()
        return {"scan_status": "skipped"}

    sub.status = "automated_review"
    sub.automated_scan_status = "pending"
    sub.updated_at = datetime.now(timezone.utc)
    db.flush()

    findings = []
    file_count = 0
    total_size = 0

    try:
        with zipfile.ZipFile(sub.artifact_path, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                file_count += 1
                total_size += info.file_size

                # Skip binary files and large files
                if info.file_size > 5 * 1024 * 1024:  # 5MB per file
                    findings.append({
                        "severity": "warning",
                        "file": info.filename,
                        "issue": f"Large file ({info.file_size} bytes) — may need manual review",
                    })
                    continue

                # Only scan text-like files
                ext = os.path.splitext(info.filename)[1].lower()
                scannable = {".py", ".js", ".ts", ".tsx", ".jsx", ".sol", ".rs", ".go", ".sh", ".yml", ".yaml", ".json", ".toml", ".env", ".cfg", ".conf"}
                if ext not in scannable:
                    continue

                try:
                    content = zf.read(info.filename).decode("utf-8", errors="ignore")
                except Exception:
                    continue

                # Check for dangerous patterns
                for pattern, description in DANGEROUS_PATTERNS:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        findings.append({
                            "severity": "warning" if "key" in description.lower() else "info",
                            "file": info.filename,
                            "issue": description,
                            "occurrences": len(matches),
                        })

                # Check for .env files with secrets
                if info.filename.endswith(".env") or ".env." in info.filename:
                    findings.append({
                        "severity": "critical",
                        "file": info.filename,
                        "issue": "Environment file found — may contain secrets",
                    })

    except zipfile.BadZipFile:
        sub.automated_scan_status = "failed"
        sub.automated_scan_result = json.dumps({"error": "Invalid ZIP file"})
        db.flush()
        return {"scan_status": "failed", "error": "Invalid ZIP"}

    # Determine pass/fail
    critical_count = sum(1 for f in findings if f["severity"] == "critical")
    has_critical = critical_count > 0

    scan_result = {
        "file_count": file_count,
        "total_size_bytes": total_size,
        "findings": findings,
        "critical_count": critical_count,
        "warning_count": sum(1 for f in findings if f["severity"] == "warning"),
        "info_count": sum(1 for f in findings if f["severity"] == "info"),
    }

    sub.automated_scan_status = "failed" if has_critical else "passed"
    sub.automated_scan_result = json.dumps(scan_result)
    # Move to awaiting human review regardless — admin makes final call
    sub.status = "submitted"
    sub.updated_at = datetime.now(timezone.utc)
    db.flush()

    return {"scan_status": sub.automated_scan_status, "findings_count": len(findings)}


# ══════════════════════════════════════════════════════════════════
# ADMIN REVIEW FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def admin_list_submissions(
    db: Session,
    status: Optional[str] = None,
    category: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Admin: list all submissions, filterable by status."""
    q = db.query(AppSubmission)
    if status:
        q = q.filter(AppSubmission.status == status)
    if category:
        q = q.filter(AppSubmission.category == category)

    total = q.count()
    offset = (page - 1) * page_size
    subs = q.order_by(desc(AppSubmission.submitted_at)).offset(offset).limit(page_size).all()

    user_ids = list({s.submitter_id for s in subs})
    users = {u.id: u.username for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}

    return {
        "submissions": [_submission_to_dict(s, users.get(s.submitter_id)) for s in subs],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def claim_submission(db: Session, submission_id: str, reviewer_id: str) -> dict:
    """Admin: claim a submission for review."""
    sub = db.query(AppSubmission).filter(AppSubmission.id == submission_id).first()
    if not sub:
        return {"error": "Submission not found"}

    if sub.status not in ("submitted", "automated_review"):
        return {"error": f"Cannot claim submission in status '{sub.status}'"}

    sub.status = "in_review"
    sub.reviewer_id = reviewer_id
    sub.review_started_at = datetime.now(timezone.utc)
    sub.updated_at = datetime.now(timezone.utc)
    db.flush()

    # Add system note
    note = SubmissionNote(
        submission_id=submission_id,
        author_id=reviewer_id,
        note_type="system",
        content="Submission claimed for review.",
    )
    db.add(note)
    db.flush()

    return {"message": "Submission claimed", "status": "in_review"}


def add_review_note(db: Session, submission_id: str, author_id: str, content: str, note_type: str = "comment") -> dict:
    """Add a note to a submission (admin or developer)."""
    sub = db.query(AppSubmission).filter(AppSubmission.id == submission_id).first()
    if not sub:
        return {"error": "Submission not found"}

    if note_type not in ("comment", "request_changes", "approval", "rejection", "system"):
        return {"error": "Invalid note_type"}

    note = SubmissionNote(
        submission_id=submission_id,
        author_id=author_id,
        note_type=note_type,
        content=content,
    )
    db.add(note)
    db.flush()

    user = db.query(User).filter(User.id == author_id).first()
    return _note_to_dict(note, user.username if user else None)


def request_changes(db: Session, submission_id: str, reviewer_id: str, reason: str) -> dict:
    """Admin: request changes from the developer."""
    sub = db.query(AppSubmission).filter(AppSubmission.id == submission_id).first()
    if not sub:
        return {"error": "Submission not found"}

    if sub.status != "in_review":
        return {"error": "Submission must be in_review to request changes"}

    sub.status = "changes_requested"
    sub.updated_at = datetime.now(timezone.utc)
    db.flush()

    add_review_note(db, submission_id, reviewer_id, reason, "request_changes")
    return {"message": "Changes requested", "status": "changes_requested"}


def approve_submission(db: Session, submission_id: str, reviewer_id: str, note: str = "") -> dict:
    """Admin: approve a submission and publish it to the App Store."""
    sub = db.query(AppSubmission).filter(AppSubmission.id == submission_id).first()
    if not sub:
        return {"error": "Submission not found"}

    if sub.status != "in_review":
        return {"error": "Submission must be in_review to approve"}

    now = datetime.now(timezone.utc)

    # Create or update the AppListing
    from api.services.app_store import publish_app, _slugify

    download_url = f"/apps/submissions/{sub.id}/download" if sub.artifact_path else None

    result = publish_app(
        db,
        owner_id=sub.submitter_id,
        name=sub.name,
        description=sub.description or "",
        category=sub.category,
        chain=sub.chain,
        version=sub.version,
        readme=sub.readme,
        icon_url=sub.icon_url,
        screenshots=json.loads(sub.screenshots) if sub.screenshots else None,
        tags=json.loads(sub.tags) if sub.tags else None,
        price_type=sub.price_type or "free",
        price_amount=sub.price_amount or 0.0,
        price_token=sub.price_token,
        license_type=sub.license_type or "open",
        download_url=download_url,
        external_url=sub.external_url,
    )

    if "error" in result:
        return result

    # Mark as verified since admin approved it
    listing = db.query(AppListing).filter(AppListing.id == result["id"]).first()
    if listing:
        listing.is_verified = True
        listing.updated_at = now

    # Update submission
    sub.status = "approved"
    sub.app_listing_id = result["id"]
    sub.review_completed_at = now
    sub.updated_at = now
    db.flush()

    if note:
        add_review_note(db, submission_id, reviewer_id, note, "approval")
    add_review_note(db, submission_id, reviewer_id, f"Approved and published as {result.get('slug', 'N/A')}", "system")

    return {"message": "Submission approved and published", "app_listing": result}


def reject_submission(db: Session, submission_id: str, reviewer_id: str, reason: str) -> dict:
    """Admin: reject a submission."""
    sub = db.query(AppSubmission).filter(AppSubmission.id == submission_id).first()
    if not sub:
        return {"error": "Submission not found"}

    if sub.status != "in_review":
        return {"error": "Submission must be in_review to reject"}

    sub.status = "rejected"
    sub.rejection_reason = reason
    sub.review_completed_at = datetime.now(timezone.utc)
    sub.updated_at = datetime.now(timezone.utc)
    db.flush()

    add_review_note(db, submission_id, reviewer_id, reason, "rejection")
    return {"message": "Submission rejected", "reason": reason}


def submission_stats(db: Session) -> dict:
    """Admin: get submission pipeline statistics."""
    total = db.query(AppSubmission).count()
    by_status = {}
    for status in VALID_STATUSES:
        by_status[status] = db.query(AppSubmission).filter(AppSubmission.status == status).count()

    pending_review = by_status.get("submitted", 0) + by_status.get("automated_review", 0)

    return {
        "total": total,
        "by_status": by_status,
        "pending_review": pending_review,
        "in_review": by_status.get("in_review", 0),
        "approved": by_status.get("approved", 0),
        "rejected": by_status.get("rejected", 0),
    }

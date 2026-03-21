"""
REFINET Cloud — Support / Help Desk Routes
Customer support ticket system with XMTP-encrypted messaging.
User endpoints: create, list, view, reply, close tickets.
Admin endpoints: list all, assign, update status, view stats.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.database import public_db_dependency, internal_db_dependency
from api.auth.jwt import decode_access_token
from api.auth.roles import is_admin

logger = logging.getLogger("refinet.support")
router = APIRouter(prefix="/support", tags=["Support"])

SUPPORT_CATEGORIES = [
    {"id": "general", "label": "General Question"},
    {"id": "bug", "label": "Bug Report"},
    {"id": "billing", "label": "Billing & Payments"},
    {"id": "security", "label": "Security Concern"},
    {"id": "feature", "label": "Feature Request"},
    {"id": "account", "label": "Account Issue"},
]


# ── Auth Helpers ────────────────────────────────────────────────────

def _get_current_user(request: Request) -> str:
    """Extract user_id from Bearer token."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = decode_access_token(auth[7:])
        return payload["sub"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def _require_admin_role(request: Request, internal_db: Session) -> str:
    """Return user_id if admin. Raises 403 otherwise."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = decode_access_token(auth[7:])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = payload["sub"]
    if not is_admin(internal_db, user_id):
        raise HTTPException(status_code=403, detail="Admin role required")
    return user_id


# ── Schemas ─────────────────────────────────────────────────────────

class CreateTicketRequest(BaseModel):
    subject: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)
    category: str = Field(default="general")
    priority: str = Field(default="normal")
    metadata: Optional[dict] = None


class ReplyRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class UpdateStatusRequest(BaseModel):
    status: str


class AssignRequest(BaseModel):
    assignee_id: str


# ── User Endpoints ──────────────────────────────────────────────────

@router.get("/categories")
def get_categories():
    """List available support ticket categories."""
    return SUPPORT_CATEGORIES


@router.post("/tickets")
def create_ticket(
    body: CreateTicketRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Create a new support ticket."""
    user_id = _get_current_user(request)
    try:
        from api.services.support import create_ticket as svc_create
        ticket = svc_create(
            db,
            user_id=user_id,
            subject=body.subject,
            description=body.description,
            category=body.category,
            priority=body.priority,
            metadata=body.metadata,
        )
        return ticket
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tickets")
def list_my_tickets(
    request: Request,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(public_db_dependency),
):
    """List my support tickets."""
    user_id = _get_current_user(request)
    from api.services.support import list_user_tickets
    return list_user_tickets(db, user_id, status=status, page=page, page_size=page_size)


@router.get("/tickets/{ticket_id}")
def get_ticket(
    ticket_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
    internal_db: Session = Depends(internal_db_dependency),
):
    """Get ticket detail with messages. Admins can view any ticket."""
    user_id = _get_current_user(request)

    # Check if admin — they can view any ticket
    is_admin_user = False
    try:
        is_admin_user = is_admin(internal_db, user_id)
    except Exception:
        pass

    from api.services.support import get_ticket as svc_get
    ticket = svc_get(
        db,
        ticket_id,
        user_id=None if is_admin_user else user_id,
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.post("/tickets/{ticket_id}/reply")
def reply_to_ticket(
    ticket_id: str,
    body: ReplyRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
    internal_db: Session = Depends(internal_db_dependency),
):
    """Reply to a support ticket."""
    user_id = _get_current_user(request)

    is_admin_user = False
    try:
        is_admin_user = is_admin(internal_db, user_id)
    except Exception:
        pass

    try:
        from api.services.support import add_message
        msg = add_message(
            db,
            ticket_id=ticket_id,
            author_id=user_id,
            content=body.content,
            is_admin=is_admin_user,
        )
        return msg
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tickets/{ticket_id}/close")
def close_ticket(
    ticket_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
):
    """Close a support ticket (user or admin)."""
    user_id = _get_current_user(request)
    try:
        from api.services.support import close_ticket as svc_close
        return svc_close(db, ticket_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Admin Endpoints ─────────────────────────────────────────────────

@router.get("/admin/tickets")
def admin_list_tickets(
    request: Request,
    status: Optional[str] = None,
    category: Optional[str] = None,
    assigned_to: Optional[str] = None,
    priority: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(public_db_dependency),
    internal_db: Session = Depends(internal_db_dependency),
):
    """Admin: list all support tickets with filters."""
    _require_admin_role(request, internal_db)
    from api.services.support import list_all_tickets
    return list_all_tickets(
        db, status=status, category=category,
        assigned_to=assigned_to, priority=priority,
        page=page, page_size=page_size,
    )


@router.get("/admin/tickets/{ticket_id}")
def admin_get_ticket(
    ticket_id: str,
    request: Request,
    db: Session = Depends(public_db_dependency),
    internal_db: Session = Depends(internal_db_dependency),
):
    """Admin: get ticket detail."""
    _require_admin_role(request, internal_db)
    from api.services.support import get_ticket as svc_get
    ticket = svc_get(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.post("/admin/tickets/{ticket_id}/reply")
def admin_reply(
    ticket_id: str,
    body: ReplyRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
    internal_db: Session = Depends(internal_db_dependency),
):
    """Admin: reply to a support ticket."""
    admin_id = _require_admin_role(request, internal_db)
    try:
        from api.services.support import add_message
        return add_message(
            db,
            ticket_id=ticket_id,
            author_id=admin_id,
            content=body.content,
            is_admin=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/admin/tickets/{ticket_id}/status")
def admin_update_status(
    ticket_id: str,
    body: UpdateStatusRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
    internal_db: Session = Depends(internal_db_dependency),
):
    """Admin: update ticket status."""
    admin_id = _require_admin_role(request, internal_db)
    try:
        from api.services.support import update_status
        return update_status(db, ticket_id, admin_id, body.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/admin/tickets/{ticket_id}/assign")
def admin_assign_ticket(
    ticket_id: str,
    body: AssignRequest,
    request: Request,
    db: Session = Depends(public_db_dependency),
    internal_db: Session = Depends(internal_db_dependency),
):
    """Admin: assign ticket to an admin user."""
    admin_id = _require_admin_role(request, internal_db)
    try:
        from api.services.support import assign_ticket
        return assign_ticket(db, ticket_id, admin_id, body.assignee_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/admin/stats")
def admin_support_stats(
    request: Request,
    db: Session = Depends(public_db_dependency),
    internal_db: Session = Depends(internal_db_dependency),
):
    """Admin: get support desk metrics."""
    _require_admin_role(request, internal_db)
    from api.services.support import get_support_stats
    return get_support_stats(db)

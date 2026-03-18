"""
REFINET Cloud — Role-Based Access Control
Roles are stored in internal.db (never exposed via public API).
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from api.models.internal import RoleAssignment, AdminAuditLog
import uuid


VALID_ROLES = {"admin", "operator", "readonly"}


def get_user_roles(db: Session, user_id: str) -> list[str]:
    """Get all active roles for a user from internal.db."""
    assignments = db.query(RoleAssignment).filter(
        RoleAssignment.user_id == user_id,
        RoleAssignment.is_active == True,  # noqa: E712
    ).all()
    return [a.role for a in assignments]


def has_role(db: Session, user_id: str, role: str) -> bool:
    """Check if a user has a specific active role."""
    return db.query(RoleAssignment).filter(
        RoleAssignment.user_id == user_id,
        RoleAssignment.role == role,
        RoleAssignment.is_active == True,  # noqa: E712
    ).first() is not None


def is_admin(db: Session, user_id: str) -> bool:
    """Check if a user has the admin role."""
    return has_role(db, user_id, "admin")


def grant_role(
    db: Session,
    user_id: str,
    role: str,
    granted_by: str,
    notes: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> RoleAssignment:
    """Grant a role to a user. Logs to admin_audit_log."""
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role}. Must be one of {VALID_ROLES}")

    # Check for existing active assignment
    existing = db.query(RoleAssignment).filter(
        RoleAssignment.user_id == user_id,
        RoleAssignment.role == role,
        RoleAssignment.is_active == True,  # noqa: E712
    ).first()

    if existing:
        raise ValueError(f"User {user_id} already has role {role}")

    assignment = RoleAssignment(
        id=str(uuid.uuid4()),
        user_id=user_id,
        role=role,
        granted_by=granted_by,
        notes=notes,
    )
    db.add(assignment)

    # Audit log (append-only)
    audit = AdminAuditLog(
        id=str(uuid.uuid4()),
        admin_username=granted_by,
        action="GRANT_ROLE",
        target_type="user",
        target_id=user_id,
        details=f'{{"role": "{role}"}}',
        ip_address=ip_address,
    )
    db.add(audit)
    db.flush()

    return assignment


def revoke_role(
    db: Session,
    user_id: str,
    role: str,
    revoked_by: str,
    ip_address: Optional[str] = None,
) -> bool:
    """Revoke a role from a user. Logs to admin_audit_log."""
    assignment = db.query(RoleAssignment).filter(
        RoleAssignment.user_id == user_id,
        RoleAssignment.role == role,
        RoleAssignment.is_active == True,  # noqa: E712
    ).first()

    if not assignment:
        return False

    assignment.is_active = False
    assignment.revoked_at = datetime.now(timezone.utc)

    # Audit log
    audit = AdminAuditLog(
        id=str(uuid.uuid4()),
        admin_username=revoked_by,
        action="REVOKE_ROLE",
        target_type="user",
        target_id=user_id,
        details=f'{{"role": "{role}"}}',
        ip_address=ip_address,
    )
    db.add(audit)
    db.flush()

    return True

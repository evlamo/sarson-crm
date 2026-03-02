"""
Audit and Activity API Router - Phase 4
Endpoints for viewing audit logs, contact field history, and revert functionality.
"""
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.auth.dependencies import get_current_user, get_admin_user
from app.models.user import User
from app.models.audit import AuditLog, ContactFieldHistory
from app.models.contact import Contact
from app.services import audit_service

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


# ── Schemas ────────────────────────────────────────────────────────────────

class AuditLogOut(BaseModel):
    id: UUID
    user_id: Optional[UUID]
    user_name: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[UUID]
    old_values: Optional[dict]
    new_values: Optional[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


class FieldHistoryOut(BaseModel):
    id: UUID
    contact_id: UUID
    field_name: str
    old_value: Optional[str]
    new_value: Optional[str]
    changed_by: Optional[UUID]
    changed_by_name: Optional[str] = None
    changed_at: datetime
    source: str

    model_config = {"from_attributes": True}


class RevertFieldRequest(BaseModel):
    field_name: str = Field(..., min_length=1, max_length=100)
    target_value: Optional[str] = None


class PaginatedAuditLogs(BaseModel):
    data: List[AuditLogOut]
    total: int
    page: int
    per_page: int


class PaginatedFieldHistory(BaseModel):
    data: List[FieldHistoryOut]
    total: int
    page: int
    per_page: int


# ── Global Activity Feed ───────────────────────────────────────────────────

@router.get("", response_model=PaginatedAuditLogs)
def list_audit_logs(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[UUID] = Query(None),
    action: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List audit logs with optional filters.
    Returns recent activity across all entities.
    """
    query = db.query(AuditLog).options(joinedload(AuditLog.user))

    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))

    total = query.count()
    logs = (
        query.order_by(desc(AuditLog.created_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    data = []
    for log in logs:
        data.append(AuditLogOut(
            id=log.id,
            user_id=log.user_id,
            user_name=log.user.full_name if log.user else None,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            old_values=log.old_values,
            new_values=log.new_values,
            created_at=log.created_at,
        ))

    return PaginatedAuditLogs(data=data, total=total, page=page, per_page=per_page)


# ── Contact-Specific Activity ──────────────────────────────────────────────

@router.get("/contacts/{contact_id}", response_model=PaginatedAuditLogs)
def get_contact_audit_logs(
    contact_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get audit logs for a specific contact."""
    # Verify contact exists
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.deleted_at.is_(None)
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    query = (
        db.query(AuditLog)
        .options(joinedload(AuditLog.user))
        .filter(
            AuditLog.entity_type == "contact",
            AuditLog.entity_id == contact_id
        )
    )

    total = query.count()
    logs = (
        query.order_by(desc(AuditLog.created_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    data = []
    for log in logs:
        data.append(AuditLogOut(
            id=log.id,
            user_id=log.user_id,
            user_name=log.user.full_name if log.user else None,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            old_values=log.old_values,
            new_values=log.new_values,
            created_at=log.created_at,
        ))

    return PaginatedAuditLogs(data=data, total=total, page=page, per_page=per_page)


# ── Contact Field History ──────────────────────────────────────────────────

@router.get("/contacts/{contact_id}/field-history", response_model=PaginatedFieldHistory)
def get_contact_field_history(
    contact_id: UUID,
    field_name: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get field-level change history for a contact."""
    # Verify contact exists
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.deleted_at.is_(None)
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    query = (
        db.query(ContactFieldHistory)
        .options(joinedload(ContactFieldHistory.changed_by_user))
        .filter(ContactFieldHistory.contact_id == contact_id)
    )

    if field_name:
        query = query.filter(ContactFieldHistory.field_name == field_name)

    total = query.count()
    history = (
        query.order_by(desc(ContactFieldHistory.changed_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    data = []
    for h in history:
        data.append(FieldHistoryOut(
            id=h.id,
            contact_id=h.contact_id,
            field_name=h.field_name,
            old_value=h.old_value,
            new_value=h.new_value,
            changed_by=h.changed_by,
            changed_by_name=h.changed_by_user.full_name if h.changed_by_user else None,
            changed_at=h.changed_at,
            source=h.source,
        ))

    return PaginatedFieldHistory(data=data, total=total, page=page, per_page=per_page)


# ── Revert Field (Admin Only) ──────────────────────────────────────────────

@router.post("/contacts/{contact_id}/revert-field")
async def revert_contact_field(
    contact_id: UUID,
    payload: RevertFieldRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """
    Revert a contact field to a previous value.
    Admin only. Logs the revert action to audit_log.
    """
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.deleted_at.is_(None)
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    field_name = payload.field_name
    target_value = payload.target_value

    # Validate field exists on Contact model
    valid_fields = {c.key for c in Contact.__table__.columns}
    if field_name not in valid_fields:
        raise HTTPException(status_code=400, detail=f"Invalid field: {field_name}")

    # Get current value
    current_value = getattr(contact, field_name)
    current_str = str(current_value) if current_value is not None else None

    # If target matches current, no-op
    if current_str == target_value:
        return {"status": "no_change", "field": field_name}

    # Apply the revert
    setattr(contact, field_name, target_value if target_value else None)
    contact.updated_at = datetime.now(timezone.utc)

    # Log to audit_log
    await audit_service.log_action(
        db=db,
        action="contact.revert_field",
        entity_type="contact",
        entity_id=str(contact_id),
        old_values={field_name: current_str},
        new_values={field_name: target_value},
        user_id=str(admin.id),
    )

    # Log to field history
    await audit_service.log_field_change(
        db=db,
        contact_id=str(contact_id),
        field_name=field_name,
        old_value=current_value,
        new_value=target_value,
        changed_by=str(admin.id),
        source="revert",
    )

    db.commit()

    return {
        "status": "reverted",
        "field": field_name,
        "old_value": current_str,
        "new_value": target_value,
    }

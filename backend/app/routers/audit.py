"""
Audit and Activity API Router - Phase 4
Endpoints for viewing audit logs, contact field history, and revert functionality.
"""
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
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


# Allowlist of fields that can be reverted (security hardening)
REVERTABLE_FIELDS = {
    "first_name", "last_name", "email", "phone", "mobile_phone",
    "title", "department", "company", "status", "source",
    "address", "city", "state", "postal_code", "country",
    "linkedin_url", "twitter_handle", "notes", "lead_score",
}


class RevertFieldRequest(BaseModel):
    field_name: str = Field(..., min_length=1, max_length=100)
    target_value: Optional[str] = None
    
    @field_validator('field_name')
    @classmethod
    def validate_field_name(cls, v):
        # Only alphanumeric and underscore allowed
        if not re.match(r'^[a-z_][a-z0-9_]*$', v):
            raise ValueError('Invalid field name format')
        # Check against allowlist
        if v not in REVERTABLE_FIELDS:
            raise ValueError(f'Field "{v}" is not revertable')
        return v
    
    @field_validator('target_value')
    @classmethod
    def validate_target_value(cls, v):
        if v is not None:
            # Prevent excessively long values
            if len(v) > 10000:
                raise ValueError('Value too long (max 10000 chars)')
            # Basic sanitization - no control characters except newline/tab
            if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', v):
                raise ValueError('Invalid characters in value')
        return v


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
    entity_type: Optional[str] = Query(None, max_length=50),
    entity_id: Optional[UUID] = Query(None),
    action: Optional[str] = Query(None, max_length=100),
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
        # Validate entity_type to prevent injection
        if not re.match(r'^[a-z_]+$', entity_type):
            raise HTTPException(status_code=400, detail="Invalid entity_type format")
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)
    if action:
        # Use exact match for action filtering
        query = query.filter(AuditLog.action == action)

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
    field_name: Optional[str] = Query(None, max_length=100),
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
        # Validate field_name format
        if not re.match(r'^[a-z_][a-z0-9_]*$', field_name):
            raise HTTPException(status_code=400, detail="Invalid field_name format")
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
def revert_contact_field(
    contact_id: UUID,
    payload: RevertFieldRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """
    Revert a contact field to a previous value.
    Admin only. Logs the revert action to audit_log.
    
    Security:
    - Admin-only access
    - Field name validated against allowlist
    - Value sanitized and length-limited
    - All reverts are logged
    """
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.deleted_at.is_(None)
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    field_name = payload.field_name
    target_value = payload.target_value

    # Double-check field exists on Contact model (belt and suspenders)
    if not hasattr(contact, field_name):
        raise HTTPException(status_code=400, detail=f"Field '{field_name}' does not exist on Contact")

    # Get current value
    current_value = getattr(contact, field_name)
    current_str = str(current_value) if current_value is not None else None

    # If target matches current, no-op
    if current_str == target_value:
        return {"status": "no_change", "field": field_name}

    # Apply the revert
    setattr(contact, field_name, target_value if target_value else None)
    contact.updated_at = datetime.now(timezone.utc)

    # Log to audit_log (sync version)
    audit_service.log_action_sync(
        db=db,
        action="contact.revert_field",
        entity_type="contact",
        entity_id=str(contact_id),
        old_values={field_name: current_str},
        new_values={field_name: target_value},
        user_id=str(admin.id),
    )

    # Log to field history (sync version)
    audit_service.log_field_change_sync(
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

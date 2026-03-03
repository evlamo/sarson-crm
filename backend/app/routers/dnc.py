"""
DNC (Do Not Contact) Management Router - Phase 2
Admin-only endpoints for managing master DNC status.
"""
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user, get_admin_user, require_not_restricted
from app.models.user import User
from app.models.contact import Contact
from app.models.sales_campaign import CampaignContact
from app.services import audit_service

router = APIRouter(prefix="/api/v1/dnc", tags=["dnc"])


def _utcnow():
    return datetime.now(timezone.utc)


# ── Schemas ────────────────────────────────────────────────────────────────

class SetDNCRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class DNCContactOut(BaseModel):
    id: UUID
    first_name: Optional[str]
    last_name: Optional[str]
    full_name: str
    email: Optional[str]
    company: Optional[str]
    master_dnc: bool
    master_dnc_reason: Optional[str]
    master_dnc_set_at: Optional[datetime]
    master_dnc_set_by: Optional[UUID]
    email_unsubscribed: bool

    model_config = {"from_attributes": True}


class PaginatedDNCContacts(BaseModel):
    data: List[DNCContactOut]
    total: int
    page: int
    per_page: int


# ── Helpers ────────────────────────────────────────────────────────────────

def _log_audit(db: Session, action: str, entity_type: str, entity_id: str, user_id: str,
               old_values: dict = None, new_values: dict = None):
    """Sync audit logging using audit_service."""
    audit_service.log_action_sync(
        db=db,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        user_id=str(user_id),
        old_values=old_values,
        new_values=new_values,
    )


def _get_contact_or_404(contact_id: UUID, db: Session) -> Contact:
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.deleted_at.is_(None)
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


# ── List All DNC Contacts ──────────────────────────────────────────────────

@router.get("", response_model=PaginatedDNCContacts)
def list_dnc_contacts(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    search: Optional[str] = Query(None, max_length=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """List all contacts on the master DNC list. Admin only."""
    query = db.query(Contact).filter(
        Contact.deleted_at.is_(None),
        Contact.master_dnc == True
    )
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Contact.first_name.ilike(search_term)) |
            (Contact.last_name.ilike(search_term)) |
            (Contact.email.ilike(search_term)) |
            (Contact.company.ilike(search_term))
        )
    
    total = query.count()
    contacts = (
        query.order_by(desc(Contact.master_dnc_set_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    
    data = [
        DNCContactOut(
            id=c.id,
            first_name=c.first_name,
            last_name=c.last_name,
            full_name=c.full_name,
            email=c.email,
            company=c.company,
            master_dnc=c.master_dnc,
            master_dnc_reason=c.master_dnc_reason,
            master_dnc_set_at=c.master_dnc_set_at,
            master_dnc_set_by=c.master_dnc_set_by,
            email_unsubscribed=c.email_unsubscribed or False,
        )
        for c in contacts
    ]
    
    return PaginatedDNCContacts(data=data, total=total, page=page, per_page=per_page)


# ── Set Master DNC ─────────────────────────────────────────────────────────

@router.post("/contacts/{contact_id}", response_model=DNCContactOut, status_code=200)
def set_contact_dnc(
    contact_id: UUID,
    data: SetDNCRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """Set master DNC status on a contact. Admin only."""
    contact = _get_contact_or_404(contact_id, db)
    
    # Fix 7: Check if contact already has DNC status
    if contact.master_dnc:
        raise HTTPException(
            status_code=409,
            detail="Contact already has Master DNC status"
        )
    
    old_dnc = contact.master_dnc
    old_reason = contact.master_dnc_reason
    
    contact.master_dnc = True
    contact.master_dnc_reason = data.reason
    contact.master_dnc_set_at = _utcnow()
    contact.master_dnc_set_by = current_user.id
    contact.updated_at = _utcnow()
    
    # Mark contact as excluded in all campaign_contacts with reason 'dnc'
    db.query(CampaignContact).filter(
        CampaignContact.contact_id == contact_id,
        CampaignContact.excluded_reason.is_(None)
    ).update({
        CampaignContact.excluded_reason: 'dnc',
        CampaignContact.status: 'excluded'
    }, synchronize_session=False)
    
    _log_audit(
        db, "contact.dnc_set", "contact", str(contact_id), str(current_user.id),
        old_values={"master_dnc": old_dnc, "master_dnc_reason": old_reason},
        new_values={"master_dnc": True, "master_dnc_reason": data.reason}
    )
    
    db.commit()
    db.refresh(contact)
    
    return DNCContactOut(
        id=contact.id,
        first_name=contact.first_name,
        last_name=contact.last_name,
        full_name=contact.full_name,
        email=contact.email,
        company=contact.company,
        master_dnc=contact.master_dnc,
        master_dnc_reason=contact.master_dnc_reason,
        master_dnc_set_at=contact.master_dnc_set_at,
        master_dnc_set_by=contact.master_dnc_set_by,
        email_unsubscribed=contact.email_unsubscribed or False,
    )


# ── Remove Master DNC ──────────────────────────────────────────────────────

@router.delete("/contacts/{contact_id}", status_code=204)
def remove_contact_dnc(
    contact_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
    _: User = Depends(require_not_restricted),
):
    """Remove master DNC status from a contact. Admin only."""
    contact = _get_contact_or_404(contact_id, db)
    
    if not contact.master_dnc:
        raise HTTPException(status_code=400, detail="Contact is not on the DNC list")
    
    old_reason = contact.master_dnc_reason
    
    contact.master_dnc = False
    contact.master_dnc_reason = None
    contact.master_dnc_set_at = None
    contact.master_dnc_set_by = None
    contact.updated_at = _utcnow()
    
    # Fix 2: Restore campaign access - clear DNC exclusions
    db.query(CampaignContact).filter(
        CampaignContact.contact_id == contact_id,
        CampaignContact.excluded_reason == 'dnc'
    ).update({
        CampaignContact.excluded_reason: None,
        CampaignContact.status: 'active'
    }, synchronize_session=False)
    
    _log_audit(
        db, "contact.dnc_removed", "contact", str(contact_id), str(current_user.id),
        old_values={"master_dnc": True, "master_dnc_reason": old_reason},
        new_values={"master_dnc": False, "master_dnc_reason": None}
    )
    
    db.commit()


# ── Get DNC Status for a Contact ───────────────────────────────────────────

@router.get("/contacts/{contact_id}", response_model=DNCContactOut)
def get_contact_dnc_status(
    contact_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get DNC status for a specific contact."""
    contact = _get_contact_or_404(contact_id, db)
    
    return DNCContactOut(
        id=contact.id,
        first_name=contact.first_name,
        last_name=contact.last_name,
        full_name=contact.full_name,
        email=contact.email,
        company=contact.company,
        master_dnc=contact.master_dnc or False,
        master_dnc_reason=contact.master_dnc_reason,
        master_dnc_set_at=contact.master_dnc_set_at,
        master_dnc_set_by=contact.master_dnc_set_by,
        email_unsubscribed=contact.email_unsubscribed or False,
    )

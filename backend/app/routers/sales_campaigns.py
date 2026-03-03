"""
Sales Campaigns API Router - Phase 2
Full CRUD for sales campaigns and campaign contacts with DNC enforcement.
"""
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID
import uuid as uuid_mod

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, desc
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.auth.dependencies import get_current_user, require_not_restricted
from app.models.user import User
from app.models.contact import Contact
from app.models.sales_campaign import SalesCampaign, CampaignContact
from app.models.campaign import EmailCampaign
from app.services import audit_service

router = APIRouter(prefix="/api/v1/sales-campaigns", tags=["sales-campaigns"])


def _utcnow():
    return datetime.now(timezone.utc)


# ── Schemas ────────────────────────────────────────────────────────────────

class SalesCampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    status: str = Field(default="active", pattern="^(active|paused|completed|archived)$")


class SalesCampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(active|paused|completed|archived)$")


class SalesCampaignOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    status: str
    owner_id: Optional[UUID]
    contact_count: int = 0
    email_campaign_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CampaignContactCreate(BaseModel):
    contact_ids: List[UUID] = Field(..., min_length=1, max_length=1000)


class CampaignContactStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(active|complete|no|excluded)$")


class CampaignContactOut(BaseModel):
    id: UUID
    contact_id: UUID
    contact_name: str
    contact_email: Optional[str]
    contact_company: Optional[str]
    status: str
    completion_status: Optional[str]
    excluded_reason: Optional[str]
    master_dnc: bool = False
    added_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedSalesCampaigns(BaseModel):
    data: List[SalesCampaignOut]
    total: int
    page: int
    per_page: int


class PaginatedCampaignContacts(BaseModel):
    data: List[CampaignContactOut]
    total: int
    page: int
    per_page: int


class AddContactsResult(BaseModel):
    added: int
    skipped_dnc: int
    skipped_existing: int
    dnc_contacts: List[str] = []


# ── Helpers ────────────────────────────────────────────────────────────────

def _check_campaign_permission(user: User):
    """Check if user can manage campaigns."""
    if user.role not in ('admin', 'owner') and not getattr(user, 'can_manage_campaigns', False):
        raise HTTPException(status_code=403, detail="Permission denied: cannot manage campaigns")


def _get_campaign_or_404(campaign_id: UUID, db: Session) -> SalesCampaign:
    campaign = db.query(SalesCampaign).filter(
        SalesCampaign.id == campaign_id,
        SalesCampaign.status != "archived"
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Sales campaign not found")
    return campaign


def _is_contact_dnc(contact: Contact) -> bool:
    """Check if contact is on master DNC list."""
    return contact.master_dnc is True


def _log_audit(db: Session, action: str, entity_type: str, entity_id: str, user_id: str, old_values: dict = None, new_values: dict = None):
    """Sync audit logging - fire and forget."""
    audit_service.log_action_sync(
        db=db,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_values=old_values,
        new_values=new_values,
        user_id=user_id,
    )


def _build_campaign_out(campaign: SalesCampaign, db: Session) -> SalesCampaignOut:
    """Build campaign response with counts."""
    contact_count = db.query(func.count(CampaignContact.id)).filter(
        CampaignContact.sales_campaign_id == campaign.id
    ).scalar() or 0
    
    email_count = db.query(func.count(EmailCampaign.id)).filter(
        EmailCampaign.sales_campaign_id == campaign.id
    ).scalar() or 0
    
    return SalesCampaignOut(
        id=campaign.id,
        name=campaign.name,
        description=campaign.description,
        status=campaign.status,
        owner_id=campaign.owner_id,
        contact_count=contact_count,
        email_campaign_count=email_count,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


# ── List Sales Campaigns ───────────────────────────────────────────────────

@router.get("", response_model=PaginatedSalesCampaigns)
def list_sales_campaigns(
    status: Optional[str] = Query(None, pattern="^(active|paused|completed)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all sales campaigns with contact and email campaign counts."""
    query = db.query(SalesCampaign).filter(SalesCampaign.status != "archived")
    
    if status:
        query = query.filter(SalesCampaign.status == status)
    
    total = query.count()
    campaigns = (
        query.order_by(desc(SalesCampaign.created_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    
    return PaginatedSalesCampaigns(
        data=[_build_campaign_out(c, db) for c in campaigns],
        total=total,
        page=page,
        per_page=per_page,
    )


# ── Create Sales Campaign ──────────────────────────────────────────────────

@router.post("", response_model=SalesCampaignOut, status_code=201)
def create_sales_campaign(
    data: SalesCampaignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new sales campaign."""
    _check_campaign_permission(current_user)
    
    campaign = SalesCampaign(
        name=data.name,
        description=data.description,
        status=data.status,
        owner_id=current_user.id,
    )
    db.add(campaign)
    
    _log_audit(db, "sales_campaign.create", "sales_campaign", str(campaign.id), 
               str(current_user.id), new_values={"name": data.name, "status": data.status})
    
    db.commit()
    db.refresh(campaign)
    return _build_campaign_out(campaign, db)


# ── Get Sales Campaign ─────────────────────────────────────────────────────

@router.get("/{campaign_id}", response_model=SalesCampaignOut)
def get_sales_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single sales campaign with stats."""
    campaign = _get_campaign_or_404(campaign_id, db)
    return _build_campaign_out(campaign, db)


# ── Update Sales Campaign ──────────────────────────────────────────────────

@router.put("/{campaign_id}", response_model=SalesCampaignOut)
def update_sales_campaign(
    campaign_id: UUID,
    data: SalesCampaignUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a sales campaign."""
    _check_campaign_permission(current_user)
    campaign = _get_campaign_or_404(campaign_id, db)
    
    old_values = {"name": campaign.name, "status": campaign.status}
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(campaign, key, value)
    
    campaign.updated_at = _utcnow()
    
    _log_audit(db, "sales_campaign.update", "sales_campaign", str(campaign_id),
               str(current_user.id), old_values=old_values, new_values=update_data)
    
    db.commit()
    db.refresh(campaign)
    return _build_campaign_out(campaign, db)


# ── Delete (Archive) Sales Campaign ────────────────────────────────────────

@router.delete("/{campaign_id}", status_code=204)
def delete_sales_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_not_restricted),
):
    """Soft delete (archive) a sales campaign."""
    _check_campaign_permission(current_user)
    campaign = _get_campaign_or_404(campaign_id, db)
    
    campaign.status = "archived"
    campaign.updated_at = _utcnow()
    
    _log_audit(db, "sales_campaign.archive", "sales_campaign", str(campaign_id),
               str(current_user.id), new_values={"status": "archived"})
    
    db.commit()


# ── List Campaign Contacts ─────────────────────────────────────────────────

@router.get("/{campaign_id}/contacts", response_model=PaginatedCampaignContacts)
def list_campaign_contacts(
    campaign_id: UUID,
    status: Optional[str] = Query(None, pattern="^(active|complete|no|excluded)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List contacts in a sales campaign with their status."""
    campaign = _get_campaign_or_404(campaign_id, db)
    
    query = (
        db.query(CampaignContact)
        .options(joinedload(CampaignContact.contact))
        .filter(CampaignContact.sales_campaign_id == campaign_id)
    )
    
    if status:
        query = query.filter(CampaignContact.status == status)
    
    total = query.count()
    records = (
        query.order_by(desc(CampaignContact.added_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    
    data = []
    for cc in records:
        contact = cc.contact
        data.append(CampaignContactOut(
            id=cc.id,
            contact_id=cc.contact_id,
            contact_name=contact.full_name if contact else "",
            contact_email=contact.email if contact else None,
            contact_company=contact.company if contact else None,
            status=cc.status,
            completion_status=cc.completion_status,
            excluded_reason=cc.excluded_reason,
            master_dnc=contact.master_dnc if contact else False,
            added_at=cc.added_at,
            updated_at=cc.updated_at,
        ))
    
    return PaginatedCampaignContacts(data=data, total=total, page=page, per_page=per_page)


# ── Add Contacts to Campaign ───────────────────────────────────────────────

@router.post("/{campaign_id}/contacts", response_model=AddContactsResult, status_code=201)
def add_contacts_to_campaign(
    campaign_id: UUID,
    data: CampaignContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add contacts to a sales campaign. DNC contacts are skipped."""
    _check_campaign_permission(current_user)
    campaign = _get_campaign_or_404(campaign_id, db)
    
    # Get existing contact IDs in this campaign
    existing_ids = set(
        row[0] for row in db.query(CampaignContact.contact_id)
        .filter(CampaignContact.sales_campaign_id == campaign_id)
        .all()
    )
    
    # Fetch all contacts
    contacts = db.query(Contact).filter(
        Contact.id.in_(data.contact_ids),
        Contact.deleted_at.is_(None)
    ).all()
    
    added = 0
    skipped_dnc = 0
    skipped_existing = 0
    dnc_contacts = []
    
    for contact in contacts:
        if contact.id in existing_ids:
            skipped_existing += 1
            continue
        
        if _is_contact_dnc(contact):
            skipped_dnc += 1
            dnc_contacts.append(contact.full_name or str(contact.id))
            continue
        
        cc = CampaignContact(
            contact_id=contact.id,
            sales_campaign_id=campaign_id,
            status="active",
        )
        db.add(cc)
        added += 1
    
    if added > 0:
        _log_audit(db, "sales_campaign.add_contacts", "sales_campaign", str(campaign_id),
                   str(current_user.id), new_values={"added": added, "skipped_dnc": skipped_dnc})
        db.commit()
    
    return AddContactsResult(
        added=added,
        skipped_dnc=skipped_dnc,
        skipped_existing=skipped_existing,
        dnc_contacts=dnc_contacts,
    )


# ── Update Contact Status in Campaign ──────────────────────────────────────

@router.put("/{campaign_id}/contacts/{contact_id}", response_model=CampaignContactOut)
def update_campaign_contact_status(
    campaign_id: UUID,
    contact_id: UUID,
    data: CampaignContactStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a contact's status in a campaign. Handles completion logic."""
    _check_campaign_permission(current_user)
    campaign = _get_campaign_or_404(campaign_id, db)
    
    cc = (
        db.query(CampaignContact)
        .options(joinedload(CampaignContact.contact))
        .filter(
            CampaignContact.sales_campaign_id == campaign_id,
            CampaignContact.contact_id == contact_id
        )
        .first()
    )
    
    if not cc:
        raise HTTPException(status_code=404, detail="Contact not found in this campaign")
    
    old_status = cc.status
    cc.status = data.status
    cc.updated_at = _utcnow()
    
    # Handle campaign completion logic
    if data.status in ("complete", "no"):
        cc.completion_status = data.status
        cc.excluded_reason = "campaign_complete"
        
        _log_audit(db, "campaign_contact.completed", "campaign_contact", str(contact_id),
                   str(current_user.id), 
                   old_values={"status": old_status},
                   new_values={"status": data.status, "sales_campaign_id": str(campaign_id)})
    else:
        _log_audit(db, "campaign_contact.status_update", "campaign_contact", str(contact_id),
                   str(current_user.id),
                   old_values={"status": old_status},
                   new_values={"status": data.status})
    
    db.commit()
    db.refresh(cc)
    
    contact = cc.contact
    return CampaignContactOut(
        id=cc.id,
        contact_id=cc.contact_id,
        contact_name=contact.full_name if contact else "",
        contact_email=contact.email if contact else None,
        contact_company=contact.company if contact else None,
        status=cc.status,
        completion_status=cc.completion_status,
        excluded_reason=cc.excluded_reason,
        master_dnc=contact.master_dnc if contact else False,
        added_at=cc.added_at,
        updated_at=cc.updated_at,
    )


# ── Remove Contact from Campaign ───────────────────────────────────────────

@router.delete("/{campaign_id}/contacts/{contact_id}", status_code=204)
def remove_contact_from_campaign(
    campaign_id: UUID,
    contact_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_not_restricted),
):
    """Remove a contact from a sales campaign."""
    _check_campaign_permission(current_user)
    campaign = _get_campaign_or_404(campaign_id, db)
    
    cc = db.query(CampaignContact).filter(
        CampaignContact.sales_campaign_id == campaign_id,
        CampaignContact.contact_id == contact_id
    ).first()
    
    if not cc:
        raise HTTPException(status_code=404, detail="Contact not found in this campaign")
    
    _log_audit(db, "sales_campaign.remove_contact", "campaign_contact", str(contact_id),
               str(current_user.id), old_values={"sales_campaign_id": str(campaign_id)})
    
    db.delete(cc)
    db.commit()


# ── Get Campaign Stats ─────────────────────────────────────────────────────

@router.get("/{campaign_id}/stats")
def get_campaign_stats(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get statistics for a sales campaign."""
    campaign = _get_campaign_or_404(campaign_id, db)
    
    total = db.query(func.count(CampaignContact.id)).filter(
        CampaignContact.sales_campaign_id == campaign_id
    ).scalar() or 0
    
    active = db.query(func.count(CampaignContact.id)).filter(
        CampaignContact.sales_campaign_id == campaign_id,
        CampaignContact.status == "active"
    ).scalar() or 0
    
    completed = db.query(func.count(CampaignContact.id)).filter(
        CampaignContact.sales_campaign_id == campaign_id,
        CampaignContact.completion_status == "complete"
    ).scalar() or 0
    
    no_count = db.query(func.count(CampaignContact.id)).filter(
        CampaignContact.sales_campaign_id == campaign_id,
        CampaignContact.completion_status == "no"
    ).scalar() or 0
    
    excluded = db.query(func.count(CampaignContact.id)).filter(
        CampaignContact.sales_campaign_id == campaign_id,
        CampaignContact.status == "excluded"
    ).scalar() or 0
    
    email_campaigns = db.query(func.count(EmailCampaign.id)).filter(
        EmailCampaign.sales_campaign_id == campaign_id
    ).scalar() or 0
    
    completion_rate = round((completed / total * 100) if total > 0 else 0, 1)
    exclusion_rate = round(((excluded + no_count) / total * 100) if total > 0 else 0, 1)
    
    return {
        "campaign_id": str(campaign_id),
        "campaign_name": campaign.name,
        "total_contacts": total,
        "active_contacts": active,
        "completed_contacts": completed,
        "no_contacts": no_count,
        "excluded_contacts": excluded,
        "email_campaigns": email_campaigns,
        "completion_rate": completion_rate,
        "exclusion_rate": exclusion_rate,
    }

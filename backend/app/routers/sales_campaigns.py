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
from sqlalchemy import func, desc, or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.contact import Contact
from app.models.tag import Tag
from app.models.static_list import StaticListMember
from app.models.sales_campaign import SalesCampaign, CampaignContact
from app.models.campaign_segment import CampaignSegment
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


class BulkAddContactsRequest(BaseModel):
    contact_ids: List[UUID] = Field(..., min_length=1, max_length=1000)
    initial_status: str = Field(default="active", pattern="^(active|paused|complete|no|excluded)$")


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


# ── Search endpoint schemas ────────────────────────────────────────────────

class ContactSearchResult(BaseModel):
    id: UUID
    full_name: str
    email: Optional[str]
    company: Optional[str]
    tags: List[str] = []
    master_dnc: bool = False

    model_config = {"from_attributes": True}


class PaginatedContactSearch(BaseModel):
    data: List[ContactSearchResult]
    total: int
    page: int
    per_page: int


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


def _log_audit(db: Session, action: str, entity_type: str, entity_id: str, user_id: str, old_values: Optional[dict] = None, new_values: Optional[dict] = None):
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
    
    # Count unique email campaigns linked through CampaignContact
    email_count = db.query(func.count(func.distinct(CampaignContact.email_campaign_id))).filter(
        CampaignContact.sales_campaign_id == campaign.id,
        CampaignContact.email_campaign_id.isnot(None)
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
    db.commit()
    db.refresh(campaign)
    
    _log_audit(db, "sales_campaign.create", "sales_campaign", str(campaign.id), 
               str(current_user.id), new_values={"name": data.name, "status": data.status})
    db.commit()
    
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
    _current_user: User = Depends(get_current_user),
):
    """Soft delete (archive) a sales campaign."""
    _check_campaign_permission(current_user)
    campaign = _get_campaign_or_404(campaign_id, db)
    
    campaign.status = "archived"
    campaign.updated_at = _utcnow()
    
    _log_audit(db, "sales_campaign.archive", "sales_campaign", str(campaign_id),
               str(current_user.id), new_values={"status": "archived"})
    
    db.commit()


# ── Search Contacts to Add ─────────────────────────────────────────────────

@router.get("/{campaign_id}/contacts/search", response_model=PaginatedContactSearch)
def search_contacts_for_campaign(
    campaign_id: UUID,
    q: Optional[str] = Query(None, max_length=300, description="Search name, email, company"),
    tag: Optional[str] = Query(None, max_length=100, description="Filter by tag name"),
    tag_id: Optional[UUID] = Query(None, description="Filter by tag ID"),
    list_id: Optional[UUID] = Query(None, description="Filter by static list ID"),
    exclude_existing: bool = Query(True, description="Exclude contacts already in campaign"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search contacts to add to a campaign.
    Supports filtering by text search, tag, and list.
    """
    # Verify campaign exists
    _get_campaign_or_404(campaign_id, db)
    
    query = (
        db.query(Contact)
        .options(joinedload(Contact.tags))
        .filter(Contact.deleted_at.is_(None))
    )
    
    # Exclude contacts already in this campaign
    if exclude_existing:
        existing_contact_ids = db.query(CampaignContact.contact_id).filter(
            CampaignContact.sales_campaign_id == campaign_id
        ).subquery()
        query = query.filter(~Contact.id.in_(existing_contact_ids))
    
    # Text search
    if q:
        search_clean = q.strip()
        search_escaped = search_clean.replace('\\', '\\\\').replace('%', r'\%').replace('_', r'\_')
        query = query.filter(
            or_(
                Contact.first_name.ilike(f"%{search_escaped}%"),
                Contact.last_name.ilike(f"%{search_escaped}%"),
                Contact.email.ilike(f"%{search_escaped}%"),
                Contact.company.ilike(f"%{search_escaped}%"),
            )
        )
    
    # Filter by tag name
    if tag:
        query = query.filter(Contact.tags.any(func.lower(Tag.name) == func.lower(tag.strip())))
    
    # Filter by tag ID
    if tag_id:
        query = query.filter(Contact.tags.any(Tag.id == tag_id))
    
    # Filter by campaign list
    if list_id:
        segment = db.query(CampaignSegment).filter(CampaignSegment.id == list_id).first()
        if segment and segment.contact_ids:
            query = query.filter(Contact.id.in_(segment.contact_ids))
        else:
            query = query.filter(False)
    
    # Get total before pagination
    total = query.count()
    
    # Apply pagination
    contacts = (
        query.order_by(Contact.last_name.asc().nullslast(), Contact.first_name.asc().nullslast())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    
    # Build response
    data = []
    for contact in contacts:
        data.append(ContactSearchResult(
            id=contact.id,
            full_name=contact.full_name or f"{contact.first_name or ''} {contact.last_name or ''}".strip(),
            email=contact.email,
            company=contact.company,
            tags=[t.name for t in contact.tags] if contact.tags else [],
            master_dnc=contact.master_dnc or False,
        ))
    
    return PaginatedContactSearch(
        data=data,
        total=total,
        page=page,
        per_page=per_page,
    )


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


# ── Bulk Add Contacts with Initial Status ──────────────────────────────────

@router.post("/{campaign_id}/contacts/bulk", response_model=AddContactsResult, status_code=201)
def bulk_add_contacts_to_campaign(
    campaign_id: UUID,
    data: BulkAddContactsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Bulk add contacts to a sales campaign with custom initial status.
    DNC contacts are skipped silently.
    """
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
            status=data.initial_status,
        )
        db.add(cc)
        added += 1
    
    if added > 0:
        _log_audit(db, "sales_campaign.bulk_add_contacts", "sales_campaign", str(campaign_id),
                   str(current_user.id), new_values={
                       "added": added, 
                       "skipped_dnc": skipped_dnc,
                       "initial_status": data.initial_status
                   })
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
    _current_user: User = Depends(get_current_user),
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
    
    email_campaigns = db.query(func.count(func.distinct(CampaignContact.email_campaign_id))).filter(
        CampaignContact.sales_campaign_id == campaign_id,
        CampaignContact.email_campaign_id.isnot(None)
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


# ── Remove Contact from Campaign ────────────────────────────────────────────

@router.post("/{campaign_id}/remove-contact", response_model=dict)
def remove_contact_from_campaign(
    campaign_id: UUID,
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Remove a contact from a sales campaign with a reason.
    
    Request body: { contact_id: UUID, reason: str, notes?: str }
    Response: CampaignContactRemovalOut
    """
    from app.schemas.campaign_contact_removal import RemoveContactRequest, CampaignContactRemovalOut
    
    # Parse request
    try:
        remove_request = RemoveContactRequest(**request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request: {str(e)}")
    
    # Get campaign
    campaign = _get_campaign_or_404(campaign_id, db)
    
    # Check permission (admin or campaign owner)
    if not (current_user.is_admin or campaign.owner_id == current_user.id):
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # Get contact to verify it exists in the campaign
    contact = db.query(Contact).filter(Contact.id == remove_request.contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Check if contact is in this campaign
    campaign_contact = db.query(CampaignContact).filter(
        CampaignContact.contact_id == remove_request.contact_id,
        CampaignContact.sales_campaign_id == campaign_id
    ).first()
    
    if not campaign_contact:
        raise HTTPException(
            status_code=404,
            detail="Contact is not part of this campaign"
        )
    
    try:
        # Call service to create removal record
        # Create removal record
        from app.models.campaign_contact_removal import CampaignContactRemoval as CCRemovalModel
        removal = CCRemovalModel(
            contact_id=remove_request.contact_id,
            sales_campaign_id=campaign_id,
            reason=remove_request.reason,
            notes=remove_request.notes,
            removed_by=current_user.id,
        )
        db.add(removal)
        db.commit()
        db.refresh(removal)
        
        # Log audit trail
        audit_service.log_action(
            db,
            current_user.id,
            "campaign_contact_removal",
            str(campaign_id),
            new_values={"contact_id": str(remove_request.contact_id), "reason": remove_request.reason},
        )
        
        # Convert to schema response
        return CampaignContactRemovalOut.model_validate(removal).model_dump()
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing contact: {str(e)}")

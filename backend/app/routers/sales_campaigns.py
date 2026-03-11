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
from sqlalchemy import func, desc, or_, literal, distinct
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
from app.schemas.campaign import PreviewRecipientsRequest

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
    return getattr(contact, "master_dnc", False) is True


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

@router.post("", status_code=201)
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
    
    return {
        "data": _build_campaign_out(campaign, db).model_dump(),
        "message": "Campaign created"
    }


# ── Get Sales Campaign ─────────────────────────────────────────────────────

@router.get("/{campaign_id}")
def get_sales_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single sales campaign with stats."""
    campaign = _get_campaign_or_404(campaign_id, db)
    
    return {"data": _build_campaign_out(campaign, db).model_dump()}


# ── Update Sales Campaign ──────────────────────────────────────────────────

@router.put("/{campaign_id}")
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
    
    return {
        "data": _build_campaign_out(campaign, db).model_dump(),
        "message": "Campaign updated"
    }


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
            master_dnc=getattr(contact, 'master_dnc', False) if contact else False,
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

@router.put("/{campaign_id}/contacts/{contact_id}")
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
    contact_out = CampaignContactOut(
        id=cc.id,
        contact_id=cc.contact_id,
        contact_name=contact.full_name if contact else "",
        contact_email=contact.email if contact else None,
        contact_company=contact.company if contact else None,
        status=cc.status,
        completion_status=cc.completion_status,
        excluded_reason=cc.excluded_reason,
        master_dnc=getattr(contact, 'master_dnc', False) if contact else False,
        added_at=cc.added_at,
        updated_at=cc.updated_at,
    )
    return {
        "data": contact_out.model_dump(),
        "message": "Contact status updated"
    }


# ── Remove Contact from Campaign ───────────────────────────────────────────

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
        "data": {
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


# ── Nested Email Campaigns ─────────────────────────────────────────────────

@router.get("/{campaign_id}/campaigns", response_model=dict)
def list_campaigns_for_sales_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
):
    """List all email campaigns for a specific sales campaign."""
    # Check that sales campaign exists
    sales_campaign = db.query(SalesCampaign).filter(SalesCampaign.id == campaign_id).first()
    if not sales_campaign:
        raise HTTPException(status_code=404, detail="Sales campaign not found")

    # Check authorization
    if current_user.role != "admin" and sales_campaign.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this campaign")

    # Query email campaigns filtered by sales_campaign_id
    total = db.query(EmailCampaign).filter(
        EmailCampaign.sales_campaign_id == campaign_id
    ).count()
    
    campaigns = db.query(EmailCampaign).filter(
        EmailCampaign.sales_campaign_id == campaign_id
    ).order_by(desc(EmailCampaign.created_at)).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    from app.schemas.campaign import CampaignOut
    campaigns_data = [CampaignOut.model_validate(c) for c in campaigns]
    
    return {
        "data": campaigns_data,
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.post("/{campaign_id}/campaigns", response_model=dict, status_code=201)
def create_campaign_for_sales_campaign(
    campaign_id: UUID,
    data: dict,  # Accept flexible payload
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new email campaign within a sales campaign."""
    # Check that sales campaign exists
    sales_campaign = db.query(SalesCampaign).filter(SalesCampaign.id == campaign_id).first()
    if not sales_campaign:
        raise HTTPException(status_code=404, detail="Sales campaign not found")

    # Check authorization
    if current_user.role != "admin" and sales_campaign.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to create campaign in this sales campaign")

    # Validate segment if provided
    if data.get("segment_id"):
        from app.models.segment import Segment
        segment = db.query(Segment).filter(Segment.id == data["segment_id"]).first()
        if not segment:
            raise HTTPException(status_code=404, detail="Segment not found")

    # Create the email campaign with sales_campaign_id automatically set
    campaign = EmailCampaign(
        name=data.get("name"),
        subject=data.get("subject"),
        preview_text=data.get("preview_text"),
        body_html=data.get("body_html"),
        body_text=data.get("body_text"),
        template_id=data.get("template_id"),
        segment_id=data.get("segment_id"),
        from_name=data.get("from_name", "Sarson Funds"),
        from_email=data.get("from_email"),
        reply_to=data.get("reply_to"),
        status="draft",
        created_by=current_user.id,
        sales_campaign_id=campaign_id,  # Set the FK automatically
    )
    
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    
    # Log audit trail
    audit_service.log_action(
        db,
        current_user.id,
        "email_campaign_create",
        str(campaign.id),
        new_values={
            "name": campaign.name,
            "sales_campaign_id": str(campaign_id),
        },
    )

    from app.schemas.campaign import CampaignOut
    return {"data": CampaignOut.model_validate(campaign)}


# ── Available Contacts (With DNC + Campaign Exclusions) ────────────────────

class AvailableContactOut(BaseModel):
    id: UUID
    full_name: str
    email: Optional[str]
    company: Optional[str]
    tags: List[dict] = []
    already_in_campaign: bool = False

    model_config = {"from_attributes": True}


class ExclusionCounts(BaseModel):
    dnc: int
    already_in_campaign: int
    completed_or_rejected: int
    total: int


class AvailableContactsResponse(BaseModel):
    contacts: List[AvailableContactOut]
    total: int
    page: int
    per_page: int
    excluded_counts: ExclusionCounts


@router.get("/{campaign_id}/available-contacts", response_model=dict)
def get_available_contacts_for_campaign(
    campaign_id: UUID,
    search: Optional[str] = Query(None, max_length=300),
    tag_ids: Optional[str] = Query(None, description="Comma-separated tag UUIDs"),
    list_ids: Optional[str] = Query(None, description="Comma-separated list UUIDs"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get contacts available to add to a campaign.
    Auto-excludes:
    - DNC contacts (unsubscribed, bounced, invalid email)
    - Contacts already in campaign with status no/complete/excluded
    
    Returns exclusion counts for UI display.
    """
    # Verify campaign exists
    _get_campaign_or_404(campaign_id, db)
    
    # Parse filter IDs
    tag_id_list = []
    if tag_ids:
        try:
            tag_id_list = [uuid_mod.UUID(tid.strip()) for tid in tag_ids.split(",") if tid.strip()]
        except ValueError:
            pass
    
    list_id_list = []
    if list_ids:
        try:
            list_id_list = [uuid_mod.UUID(lid.strip()) for lid in list_ids.split(",") if lid.strip()]
        except ValueError:
            pass
    
    # ── Calculate exclusion counts ──
    
    # DNC count: unsubscribed OR bounced OR invalid email OR no email
    dnc_count = db.query(func.count(Contact.id)).filter(
        Contact.deleted_at.is_(None),
        or_(
            Contact.email_unsubscribed == True,
            Contact.email_bounced == True,
            Contact.email_valid == False,
            Contact._email_encrypted.is_(None),
        )
    ).scalar() or 0
    
    # Already in campaign (any status - for awareness)
    already_in_campaign = db.query(func.count(CampaignContact.id)).filter(
        CampaignContact.sales_campaign_id == campaign_id
    ).scalar() or 0
    
    # Completed or rejected in this campaign
    completed_or_rejected = db.query(func.count(CampaignContact.id)).filter(
        CampaignContact.sales_campaign_id == campaign_id,
        CampaignContact.status.in_(["no", "complete", "excluded"])
    ).scalar() or 0
    
    # ── Build main query ──
    
    # Subquery: contact IDs already in this campaign with excluded statuses
    excluded_contact_ids = db.query(CampaignContact.contact_id).filter(
        CampaignContact.sales_campaign_id == campaign_id,
        CampaignContact.status.in_(["no", "complete", "excluded"])
    ).subquery()
    
    # Subquery: contact IDs already in this campaign (any status)
    all_campaign_contact_ids = db.query(CampaignContact.contact_id).filter(
        CampaignContact.sales_campaign_id == campaign_id
    ).subquery()
    
    # Base query: valid, non-DNC contacts not excluded from this campaign
    query = (
        db.query(Contact)
        .options(joinedload(Contact.tags))
        .filter(
            Contact.deleted_at.is_(None),
            Contact.email_unsubscribed != True,
            Contact.email_bounced != True,
            Contact.email_valid == True,
            Contact._email_encrypted.isnot(None),
            ~Contact.id.in_(excluded_contact_ids),
        )
    )
    
    # Apply search filter
    if search:
        search_clean = search.strip()
        search_escaped = search_clean.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
        query = query.filter(
            or_(
                Contact.first_name.ilike(f"%{search_escaped}%"),
                Contact.last_name.ilike(f"%{search_escaped}%"),
                Contact._email_encrypted.ilike(f"%{search_escaped}%"),
                Contact.company.ilike(f"%{search_escaped}%"),
            )
        )
    
    # Apply tag filter (OR logic)
    if tag_id_list:
        query = query.filter(Contact.tags.any(Tag.id.in_(tag_id_list)))
    
    # Apply list filter (OR logic)
    if list_id_list:
        # Get contact IDs from static list members
        list_contact_ids = db.query(StaticListMember.c.contact_id).filter(
            StaticListMember.c.list_id.in_(list_id_list)
        ).subquery()
        query = query.filter(Contact.id.in_(list_contact_ids))
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    contacts = (
        query.order_by(Contact.last_name.asc().nullslast(), Contact.first_name.asc().nullslast())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    
    # Check which contacts are already in campaign (active status)
    already_in_ids = set(
        row[0] for row in db.query(CampaignContact.contact_id)
        .filter(
            CampaignContact.sales_campaign_id == campaign_id,
            CampaignContact.status == "active"
        )
        .all()
    )
    
    # Build response
    contact_data = []
    for contact in contacts:
        name_parts = []
        if contact.first_name:
            name_parts.append(contact.first_name)
        if contact.last_name:
            name_parts.append(contact.last_name)
        full_name = contact.full_name or " ".join(name_parts) or "Unknown"
        
        contact_data.append(AvailableContactOut(
            id=contact.id,
            full_name=full_name,
            email=contact.email,
            company=contact.company,
            tags=[{"id": str(t.id), "name": t.name} for t in (contact.tags or [])],
            already_in_campaign=contact.id in already_in_ids,
        ))
    
    return {
        "data": {
            "contacts": [c.model_dump() for c in contact_data],
            "total": total,
            "page": page,
            "per_page": per_page,
            "excluded_counts": {
                "dnc": dnc_count,
                "already_in_campaign": already_in_campaign,
                "completed_or_rejected": completed_or_rejected,
                "total": dnc_count + completed_or_rejected,
            }
        }
    }

# -- Preview Campaign Recipients

@router.post("/{campaign_id}/preview-recipients", response_model=dict)
def preview_campaign_recipients(
    campaign_id: UUID,
    body: PreviewRecipientsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview contacts that will be added to campaign."""
    body.validate_combine_mode()
    campaign = _get_campaign_or_404(campaign_id, db)
    
    queries = []
    
    if body.list_ids:
        list_q = (
            db.query(
                Contact.id,
                Contact.full_name,
                Contact.email,
                Contact._email_encrypted,
                Contact.company,
                Contact.email_unsubscribed,
                Contact.email_bounced,
                Contact.email_valid,
                literal("list").label("source_type"),
                literal("List").label("source_name")
            )
            .join(StaticListMember, Contact.id == StaticListMember.c.contact_id)
            .filter(StaticListMember.c.list_id.in_(body.list_ids))
            .distinct(Contact.id)
        )
        queries.append(("list", list_q))
    
    if body.tag_ids:
        tag_q = (
            db.query(
                Contact.id,
                Contact.full_name,
                Contact.email,
                Contact._email_encrypted,
                Contact.company,
                Contact.email_unsubscribed,
                Contact.email_bounced,
                Contact.email_valid,
                literal("tag").label("source_type"),
                literal("Tag").label("source_name")
            )
            .join(Tag, Contact.tags.contains(Tag))
            .filter(Tag.id.in_(body.tag_ids))
            .distinct(Contact.id)
        )
        queries.append(("tag", tag_q))
    
    if body.contact_ids:
        direct_q = (
            db.query(
                Contact.id,
                Contact.full_name,
                Contact.email,
                Contact._email_encrypted,
                Contact.company,
                Contact.email_unsubscribed,
                Contact.email_bounced,
                Contact.email_valid,
                literal("direct").label("source_type"),
                literal("Direct").label("source_name")
            )
            .filter(Contact.id.in_(body.contact_ids))
        )
        queries.append(("direct", direct_q))
    
    if not queries:
        return {"data": {
            "total_matching": 0,
            "exclusions": {"unsubscribed": 0, "bounced": 0, "invalid_email": 0, "no_email": 0, "already_in_campaign": 0, "total": 0},
            "final_count": 0,
            "sample_contacts": [],
            "breakdown": {"from_lists": 0, "from_tags": 0, "from_direct": 0, "overlap": 0}
        }}
    
    all_matching_ids = set()
    source_map = {}
    
    for source_type, query in queries:
        results = query.all()
        for row in results:
            contact_id = row[0]
            all_matching_ids.add(contact_id)
            if contact_id not in source_map:
                source_map[contact_id] = {
                    "full_name": row[1],
                    "email": row[2],
                    "company": row[4],
                    "email_unsubscribed": row[5],
                    "email_bounced": row[6],
                    "email_valid": row[7],
                    "sources": []
                }
            source = source_type.title() + ": " + ("List" if source_type == "list" else "Tag" if source_type == "tag" else "Direct")
            source_map[contact_id]["sources"].append(source)
    
    total_matching = len(all_matching_ids)
    
    if body.combine_mode == "all" and len(queries) > 1:
        filtered_ids = set(row[0] for row in queries[0][1].all())
        for source_type, query in queries[1:]:
            filtered_ids = filtered_ids.intersection(set(row[0] for row in query.all()))
        final_ids = filtered_ids
    else:
        final_ids = all_matching_ids
    
    exclusions = {
        "unsubscribed": 0,
        "bounced": 0,
        "invalid_email": 0,
        "no_email": 0,
        "already_in_campaign": 0
    }
    
    valid_ids = set()
    for contact_id in final_ids:
        info = source_map[contact_id]
        if info["email_unsubscribed"]:
            exclusions["unsubscribed"] += 1
        elif info["email_bounced"]:
            exclusions["bounced"] += 1
        elif not info["email_valid"]:
            exclusions["invalid_email"] += 1
        elif not info.get("email"):
            exclusions["no_email"] += 1
        else:
            valid_ids.add(contact_id)
    
    existing_ids = set()
    if valid_ids:
        existing_ids = set(
            row[0] for row in db.query(CampaignContact.contact_id)
            .filter(CampaignContact.contact_id.in_(valid_ids))
            .filter(CampaignContact.sales_campaign_id == campaign_id)
            .filter(CampaignContact.status.in_(["no", "complete", "excluded"]))
            .all()
        )
    
    exclusions["already_in_campaign"] = len(existing_ids)
    final_valid_ids = valid_ids - existing_ids
    final_count = len(final_valid_ids)
    
    exclusions["total"] = sum(exclusions.values())
    
    sample_contacts = []
    for i, contact_id in enumerate(sorted(final_valid_ids)):
        if i >= 10:
            break
        info = source_map[contact_id]
        sample_contacts.append({
            "id": str(contact_id),
            "full_name": info.get("full_name"),
            "email": info.get("email"),
            "company": info.get("company") or "",
            "sources": info.get("sources", [])
        })
    
    from_lists = sum(1 for cid in final_valid_ids if any("list" in s.lower() for s in source_map[cid]["sources"]))
    from_tags = sum(1 for cid in final_valid_ids if any("tag" in s.lower() for s in source_map[cid]["sources"]))
    from_direct = sum(1 for cid in final_valid_ids if any("direct" in s.lower() for s in source_map[cid]["sources"]))
    
    return {"data": {
        "total_matching": total_matching,
        "exclusions": exclusions,
        "final_count": final_count,
        "sample_contacts": sample_contacts,
        "breakdown": {"from_lists": from_lists, "from_tags": from_tags, "from_direct": from_direct, "overlap": 0}
    }}

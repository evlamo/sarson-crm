"""
Email Campaigns Hierarchy Router - Phase 2
Additional endpoints for email campaigns within the sales campaign hierarchy.
This extends the existing campaigns.py router with hierarchy-aware endpoints.
"""
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, desc, or_, and_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.auth.dependencies import get_current_user, require_not_restricted
from app.models.user import User
from app.models.contact import Contact
from app.models.sales_campaign import SalesCampaign, CampaignContact
from app.models.campaign import EmailCampaign
from app.services import audit_service

router = APIRouter(prefix="/api/v1/email-campaigns", tags=["email-campaigns"])


def _utcnow():
    return datetime.now(timezone.utc)


# ── Schemas ────────────────────────────────────────────────────────────────

class EmailCampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    subject: str = Field(..., min_length=1, max_length=500)
    preview_text: Optional[str] = Field(None, max_length=500)
    body_html: str
    body_text: Optional[str] = None
    from_name: str = Field(default="Sarson Funds")
    from_email: str = Field(default="info@sarsonfunds.com")
    reply_to: Optional[str] = None
    sales_campaign_id: Optional[UUID] = None
    template_id: Optional[UUID] = None
    segment_id: Optional[UUID] = None


class EmailCampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    subject: Optional[str] = Field(None, min_length=1, max_length=500)
    preview_text: Optional[str] = Field(None, max_length=500)
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    from_name: Optional[str] = None
    from_email: Optional[str] = None
    reply_to: Optional[str] = None
    sales_campaign_id: Optional[UUID] = None
    status: Optional[str] = Field(None, pattern="^(draft|scheduled|sending|sent|cancelled)$")


class EmailCampaignOut(BaseModel):
    id: UUID
    name: str
    subject: str
    preview_text: Optional[str]
    status: str
    sales_campaign_id: Optional[UUID]
    sales_campaign_name: Optional[str] = None
    from_name: str
    from_email: str
    reply_to: Optional[str]
    recipient_count: int
    sent_count: int
    delivered_count: int
    open_count: int
    unique_opens: int
    click_count: int
    unique_clicks: int
    bounce_count: int
    unsubscribe_count: int
    scheduled_at: Optional[datetime]
    sent_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EligibleContactOut(BaseModel):
    id: UUID
    first_name: Optional[str]
    last_name: Optional[str]
    full_name: str
    email: Optional[str]
    company: Optional[str]
    status: str

    model_config = {"from_attributes": True}


class PaginatedEmailCampaigns(BaseModel):
    data: List[EmailCampaignOut]
    total: int
    page: int
    per_page: int


class PaginatedEligibleContacts(BaseModel):
    data: List[EligibleContactOut]
    total: int
    page: int
    per_page: int
    excluded_count: int


# ── Helpers ────────────────────────────────────────────────────────────────

def _check_campaign_permission(user: User):
    """Check if user can manage campaigns."""
    if user.role != "admin" and not getattr(user, "can_manage_campaigns", False):
        raise HTTPException(status_code=403, detail="Permission denied: cannot manage campaigns")


def _get_email_campaign_or_404(campaign_id: UUID, db: Session) -> EmailCampaign:
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Email campaign not found")
    return campaign


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


def _build_email_campaign_out(ec: EmailCampaign, db: Session) -> EmailCampaignOut:
    """Build email campaign response with sales campaign name."""
    sales_campaign_name = None
    if ec.sales_campaign_id:
        sc = db.query(SalesCampaign.name).filter(SalesCampaign.id == ec.sales_campaign_id).first()
        if sc:
            sales_campaign_name = sc.name
    
    return EmailCampaignOut(
        id=ec.id,
        name=ec.name,
        subject=ec.subject,
        preview_text=ec.preview_text,
        status=ec.status,
        sales_campaign_id=ec.sales_campaign_id,
        sales_campaign_name=sales_campaign_name,
        from_name=ec.from_name,
        from_email=ec.from_email,
        reply_to=ec.reply_to,
        recipient_count=ec.recipient_count or 0,
        sent_count=ec.sent_count or 0,
        delivered_count=ec.delivered_count or 0,
        open_count=ec.open_count or 0,
        unique_opens=ec.unique_opens or 0,
        click_count=ec.click_count or 0,
        unique_clicks=ec.unique_clicks or 0,
        bounce_count=ec.bounce_count or 0,
        unsubscribe_count=ec.unsubscribe_count or 0,
        scheduled_at=ec.scheduled_at,
        sent_at=ec.sent_at,
        created_at=ec.created_at,
        updated_at=ec.updated_at,
    )


# ── List Email Campaigns ───────────────────────────────────────────────────

@router.get("", response_model=PaginatedEmailCampaigns)
def list_email_campaigns(
    sales_campaign_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None, pattern="^(draft|scheduled|sending|sent|cancelled)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List email campaigns, optionally filtered by sales campaign."""
    query = db.query(EmailCampaign)
    
    if sales_campaign_id:
        query = query.filter(EmailCampaign.sales_campaign_id == sales_campaign_id)
    
    if status:
        query = query.filter(EmailCampaign.status == status)
    
    total = query.count()
    campaigns = (
        query.order_by(desc(EmailCampaign.created_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    
    return PaginatedEmailCampaigns(
        data=[_build_email_campaign_out(c, db) for c in campaigns],
        total=total,
        page=page,
        per_page=per_page,
    )


# ── Create Email Campaign ──────────────────────────────────────────────────

@router.post("", response_model=EmailCampaignOut, status_code=201)
def create_email_campaign(
    data: EmailCampaignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new email campaign, optionally linked to a sales campaign."""
    _check_campaign_permission(current_user)
    
    # Validate sales campaign exists if provided
    if data.sales_campaign_id:
        sc = db.query(SalesCampaign).filter(
            SalesCampaign.id == data.sales_campaign_id,
            SalesCampaign.status != "archived"
        ).first()
        if not sc:
            raise HTTPException(status_code=404, detail="Sales campaign not found")
    
    campaign = EmailCampaign(
        name=data.name,
        subject=data.subject,
        preview_text=data.preview_text,
        body_html=data.body_html,
        body_text=data.body_text,
        from_name=data.from_name,
        from_email=data.from_email,
        reply_to=data.reply_to,
        sales_campaign_id=data.sales_campaign_id,
        template_id=data.template_id,
        segment_id=data.segment_id,
        status="draft",
        created_by=current_user.id,
    )
    db.add(campaign)
    
    _log_audit(db, "email_campaign.create", "email_campaign", str(campaign.id),
               str(current_user.id), new_values={"name": data.name, "sales_campaign_id": str(data.sales_campaign_id) if data.sales_campaign_id else None})
    
    db.commit()
    db.refresh(campaign)
    return _build_email_campaign_out(campaign, db)


# ── Get Email Campaign ─────────────────────────────────────────────────────

@router.get("/{campaign_id}", response_model=EmailCampaignOut)
def get_email_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single email campaign."""
    campaign = _get_email_campaign_or_404(campaign_id, db)
    return _build_email_campaign_out(campaign, db)


# ── Update Email Campaign ──────────────────────────────────────────────────

@router.put("/{campaign_id}", response_model=EmailCampaignOut)
def update_email_campaign(
    campaign_id: UUID,
    data: EmailCampaignUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an email campaign."""
    _check_campaign_permission(current_user)
    campaign = _get_email_campaign_or_404(campaign_id, db)
    
    if campaign.status not in ("draft", "scheduled"):
        raise HTTPException(status_code=400, detail="Can only edit draft or scheduled campaigns")
    
    # Validate sales campaign if changing
    update_data = data.model_dump(exclude_unset=True)
    if "sales_campaign_id" in update_data and update_data["sales_campaign_id"]:
        sc = db.query(SalesCampaign).filter(
            SalesCampaign.id == update_data["sales_campaign_id"],
            SalesCampaign.status != "archived"
        ).first()
        if not sc:
            raise HTTPException(status_code=404, detail="Sales campaign not found")
    
    for key, value in update_data.items():
        setattr(campaign, key, value)
    
    campaign.updated_at = _utcnow()
    
    _log_audit(db, "email_campaign.update", "email_campaign", str(campaign_id),
               str(current_user.id), new_values=update_data)
    
    db.commit()
    db.refresh(campaign)
    return _build_email_campaign_out(campaign, db)


# ── Delete Email Campaign ──────────────────────────────────────────────────

@router.delete("/{campaign_id}", status_code=204)
def delete_email_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_not_restricted),
):
    """Soft delete an email campaign (set status to cancelled)."""
    _check_campaign_permission(current_user)
    campaign = _get_email_campaign_or_404(campaign_id, db)
    
    if campaign.status == "sending":
        raise HTTPException(status_code=400, detail="Cannot delete a campaign that is currently sending")
    
    campaign.status = "cancelled"
    campaign.updated_at = _utcnow()
    
    _log_audit(db, "email_campaign.delete", "email_campaign", str(campaign_id),
               str(current_user.id), new_values={"status": "cancelled"})
    
    db.commit()


# ── Get Eligible Contacts for Email Campaign ───────────────────────────────
# Fix 1: Optimized single JOIN query - no N+1

@router.get("/{campaign_id}/eligible-contacts", response_model=PaginatedEligibleContacts)
def get_eligible_contacts(
    campaign_id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get contacts eligible for this email campaign.
    
    Eligibility rules (single optimized JOIN query):
    1. Contact must be in the parent sales campaign (if linked)
    2. Contact must NOT be master DNC
    3. Contact must NOT be email unsubscribed
    4. Contact must NOT have completion_status of 'complete' or 'no' in the parent sales campaign
    5. Contact must have a valid email address
    
    This is the critical endpoint for determining who can receive an email.
    """
    campaign = _get_email_campaign_or_404(campaign_id, db)
    
    if not campaign.sales_campaign_id:
        # No sales campaign linked - return empty or use segment logic
        return PaginatedEligibleContacts(
            data=[],
            total=0,
            page=page,
            per_page=per_page,
            excluded_count=0,
        )
    
    # Fix 1 & Fix 4: Single JOIN query with all filters
    # This replaces the subquery approach with a direct JOIN for efficiency
    eligible_query = (
        db.query(Contact)
        .join(CampaignContact, Contact.id == CampaignContact.contact_id)
        .filter(
            CampaignContact.sales_campaign_id == campaign.sales_campaign_id,
            Contact.deleted_at.is_(None),
            Contact.master_dnc != True,
            Contact.email_unsubscribed != True,
            Contact.email.isnot(None),
            # Fix 4: Exclude completed/no contacts from this campaign
            or_(
                CampaignContact.completion_status.is_(None),
                ~CampaignContact.completion_status.in_(["complete", "no"])
            ),
            # Also exclude those with 'dnc' exclusion reason
            or_(
                CampaignContact.excluded_reason.is_(None),
                CampaignContact.excluded_reason != 'dnc'
            )
        )
    )
    
    # Count total in sales campaign for excluded calculation
    total_in_campaign = (
        db.query(func.count(CampaignContact.id))
        .filter(CampaignContact.sales_campaign_id == campaign.sales_campaign_id)
        .scalar() or 0
    )
    
    total_eligible = eligible_query.count()
    excluded_count = total_in_campaign - total_eligible
    
    contacts = (
        eligible_query
        .order_by(Contact.last_name.asc().nullslast(), Contact.first_name.asc().nullslast())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    
    data = [
        EligibleContactOut(
            id=c.id,
            first_name=c.first_name,
            last_name=c.last_name,
            full_name=c.full_name,
            email=c.email,
            company=c.company,
            status=c.status,
        )
        for c in contacts
    ]
    
    return PaginatedEligibleContacts(
        data=data,
        total=total_eligible,
        page=page,
        per_page=per_page,
        excluded_count=excluded_count,
    )


# ── Get Eligible Contacts by Sales Campaign ID (alternate endpoint) ────────

@router.get("/eligible-contacts", response_model=PaginatedEligibleContacts)
def get_eligible_contacts_by_sales_campaign(
    sales_campaign_id: UUID = Query(..., description="Sales campaign ID to get eligible contacts for"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get contacts eligible for email campaigns within a sales campaign.
    
    This is an alternative to the /{campaign_id}/eligible-contacts endpoint
    when you want to check eligibility at the sales campaign level.
    """
    # Verify sales campaign exists
    sc = db.query(SalesCampaign).filter(SalesCampaign.id == sales_campaign_id).first()
    if not sc:
        raise HTTPException(status_code=404, detail="Sales campaign not found")
    
    # Single JOIN query - no N+1
    eligible_query = (
        db.query(Contact)
        .join(CampaignContact, Contact.id == CampaignContact.contact_id)
        .filter(
            CampaignContact.sales_campaign_id == sales_campaign_id,
            Contact.deleted_at.is_(None),
            Contact.master_dnc != True,
            Contact.email_unsubscribed != True,
            Contact.email.isnot(None),
            or_(
                CampaignContact.completion_status.is_(None),
                ~CampaignContact.completion_status.in_(["complete", "no"])
            ),
            or_(
                CampaignContact.excluded_reason.is_(None),
                CampaignContact.excluded_reason != 'dnc'
            )
        )
    )
    
    total_in_campaign = (
        db.query(func.count(CampaignContact.id))
        .filter(CampaignContact.sales_campaign_id == sales_campaign_id)
        .scalar() or 0
    )
    
    total_eligible = eligible_query.count()
    excluded_count = total_in_campaign - total_eligible
    
    contacts = (
        eligible_query
        .order_by(Contact.last_name.asc().nullslast(), Contact.first_name.asc().nullslast())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    
    data = [
        EligibleContactOut(
            id=c.id,
            first_name=c.first_name,
            last_name=c.last_name,
            full_name=c.full_name,
            email=c.email,
            company=c.company,
            status=c.status,
        )
        for c in contacts
    ]
    
    return PaginatedEligibleContacts(
        data=data,
        total=total_eligible,
        page=page,
        per_page=per_page,
        excluded_count=excluded_count,
    )

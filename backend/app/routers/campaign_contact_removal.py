"""
Campaign Contact Removal Router - Phase 8
Endpoints for removing contacts from campaigns with reason tracking.

SECURITY AUDIT NOTES:
- ✅ Auth check: @get_current_user enforced
- ✅ Input validation: Pydantic schemas + reason length
- ⚠️ CRITICAL: Rate limiting NOT implemented - needs slowapi middleware
- ✅ Authorization: User ownership verified via campaign ownership
"""
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user, get_admin_user
from app.models.user import User
from app.models.sales_campaign import SalesCampaign, CampaignContact
from app.models.campaign_removal import CampaignContactRemoval
from app.models.contact import Contact
from app.services import audit_service

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaign-removal"])


def _utcnow():
    return datetime.now(timezone.utc)


# ── Schemas ────────────────────────────────────────────────────────────────

class RemoveContactRequest(BaseModel):
    """Request schema for removing a contact from a campaign"""
    reason: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Reason for removing contact from campaign"
    )


class CampaignRemovalOut(BaseModel):
    """Response schema for campaign removal history"""
    id: UUID
    campaign_id: UUID
    contact_id: UUID
    reason: str
    removed_by_id: Optional[UUID] = None
    removed_by_email: Optional[str] = None
    removed_at: datetime

    model_config = {"from_attributes": True}


class CampaignHistoryOut(BaseModel):
    """Campaign history for a contact"""
    removal_id: UUID
    campaign_id: UUID
    campaign_name: str
    reason: str
    removed_at: datetime
    removed_by_email: Optional[str] = None


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/{campaign_id}/remove-contact", status_code=200, response_model=CampaignRemovalOut)
def remove_contact_from_campaign(
    campaign_id: UUID,
    request: RemoveContactRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    contact_id: UUID = Query(...)
) -> CampaignRemovalOut:
    """
    Remove a contact from a campaign with reason tracking.
    
    SECURITY NOTES:
    - Requires authentication
    - Verifies user owns the campaign (authorization check)
    - Input validation on reason (5-500 chars)
    - Audit logged
    """
    # ✅ AUTH CHECK: User must be authenticated (enforced by dependency)
    
    # ✅ Verify campaign exists
    campaign = db.query(SalesCampaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # ✅ AUTHORIZATION: Check user owns the campaign
    if campaign.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to manage this campaign")
    
    # ✅ Verify contact exists
    contact = db.query(Contact).filter_by(id=contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # ✅ Verify contact is in the campaign
    campaign_contact = db.query(CampaignContact).filter_by(
        campaign_id=campaign_id,
        contact_id=contact_id
    ).first()
    if not campaign_contact:
        raise HTTPException(status_code=400, detail="Contact is not in this campaign")
    
    # ✅ Input validation: reason already validated by Pydantic (5-500 chars)
    # Sanitize reason to prevent injection
    reason_sanitized = request.reason.strip()
    if len(reason_sanitized) < 5:
        raise HTTPException(status_code=400, detail="Reason must be at least 5 characters")
    
    try:
        # Create removal record
        removal = CampaignContactRemoval(
            campaign_id=campaign_id,
            contact_id=contact_id,
            reason=reason_sanitized,
            removed_by_id=current_user.id,
            removed_at=_utcnow()
        )
        db.add(removal)
        
        # Soft-delete from campaign (mark status as excluded)
        campaign_contact.status = "excluded"
        campaign_contact.excluded_reason = "manual_removal"
        campaign_contact.updated_at = _utcnow()
        
        # Audit log
        audit_service.log_action(
            db=db,
            user=current_user,
            action="remove_contact_from_campaign",
            resource_type="campaign_contact_removal",
            resource_id=str(removal.id),
            changes={"reason": reason_sanitized, "contact_id": str(contact_id)}
        )
        
        db.commit()
        
        return CampaignRemovalOut(
            id=removal.id,
            campaign_id=removal.campaign_id,
            contact_id=removal.contact_id,
            reason=removal.reason,
            removed_by_id=removal.removed_by_id,
            removed_by_email=current_user.email,
            removed_at=removal.removed_at
        )
    except Exception as e:
        db.rollback()
        # Don't expose internal error details
        raise HTTPException(
            status_code=500,
            detail="Failed to remove contact from campaign"
        )


@router.get("/contacts/{contact_id}/campaign-history", response_model=List[CampaignHistoryOut])
def get_contact_campaign_removal_history(
    contact_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
) -> List[CampaignHistoryOut]:
    """
    Get removal history for a contact across all campaigns.
    
    SECURITY NOTES:
    - Requires authentication
    - ✅ FIXED: Authorization check verifies user owns contact's company
    - Paginated to prevent DoS
    - Returns removal reasons and timestamps
    """
    # ✅ AUTH CHECK: User must be authenticated (enforced by dependency)
    
    # ✅ Verify contact exists
    contact = db.query(Contact).filter_by(id=contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # ✅ AUTHORIZATION CHECK: User can only view history for contacts in their company
    # Admin users can view all contacts' histories
    is_admin = current_user.role == "admin"
    is_same_company = contact.company_id == current_user.company_id if contact.company_id else False
    
    if not is_admin and not is_same_company:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to view this contact's history"
        )
    
    # Fetch removal history
    removals = db.query(CampaignContactRemoval).filter_by(
        contact_id=contact_id
    ).order_by(
        desc(CampaignContactRemoval.removed_at)
    ).limit(limit).offset(offset).all()
    
    result = []
    for removal in removals:
        campaign = db.query(SalesCampaign).filter_by(id=removal.campaign_id).first()
        removed_by_email = None
        if removal.removed_by_id:
            removed_user = db.query(User).filter_by(id=removal.removed_by_id).first()
            if removed_user:
                removed_by_email = removed_user.email
        
        result.append(CampaignHistoryOut(
            removal_id=removal.id,
            campaign_id=removal.campaign_id,
            campaign_name=campaign.name if campaign else "Unknown",
            reason=removal.reason,
            removed_at=removal.removed_at,
            removed_by_email=removed_by_email
        ))
    
    return result


@router.post("/{campaign_id}/contacts/{contact_id}/restore", status_code=200)
def restore_contact_to_campaign(
    campaign_id: UUID,
    contact_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Restore a removed contact back to a campaign.
    Removes the removal record and re-activates the contact in the campaign.
    """
    # ✅ AUTH CHECK: User must be authenticated
    
    # ✅ Verify campaign exists and user owns it
    campaign = db.query(SalesCampaign).filter_by(id=campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to manage this campaign")
    
    # ✅ Verify removal exists
    removal = db.query(CampaignContactRemoval).filter_by(
        campaign_id=campaign_id,
        contact_id=contact_id
    ).first()
    if not removal:
        raise HTTPException(status_code=404, detail="No removal record found")
    
    try:
        # Remove the removal record
        db.delete(removal)
        
        # Restore contact in campaign
        campaign_contact = db.query(CampaignContact).filter_by(
            campaign_id=campaign_id,
            contact_id=contact_id
        ).first()
        if campaign_contact:
            campaign_contact.status = "active"
            campaign_contact.excluded_reason = None
            campaign_contact.updated_at = _utcnow()
        
        # Audit log
        audit_service.log_action(
            db=db,
            user=current_user,
            action="restore_contact_to_campaign",
            resource_type="campaign_contact",
            resource_id=str(campaign_id),
            changes={"contact_id": str(contact_id)}
        )
        
        db.commit()
        return {"message": "Contact restored to campaign"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to restore contact"
        )

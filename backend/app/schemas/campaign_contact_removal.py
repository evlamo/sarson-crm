"""Pydantic schemas for campaign contact removal."""
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field


class RemoveContactRequest(BaseModel):
    """Request to remove a contact from a campaign."""
    contact_id: UUID = Field(..., description="Contact to remove")
    reason: str = Field(..., min_length=1, max_length=50, description="Removal reason: dnc, completed, no_response, invalid_email")
    notes: Optional[str] = Field(None, max_length=1000, description="Optional additional context")


class CampaignContactRemovalOut(BaseModel):
    """Response for a campaign contact removal."""
    id: UUID
    contact_id: UUID
    sales_campaign_id: UUID
    reason: str
    notes: Optional[str]
    removed_by: Optional[UUID]
    removed_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class CampaignHistoryItem(BaseModel):
    """A single campaign in a contact's history."""
    campaign_id: UUID
    campaign_name: str
    contact_id: UUID
    status: str  # active, complete, no, excluded
    completion_status: Optional[str]  # complete, no
    excluded_reason: Optional[str]  # dnc, campaign_complete, campaign_no, manual
    added_at: datetime
    updated_at: datetime
    removal_reason: Optional[str]  # From CampaignContactRemoval table
    removal_notes: Optional[str]
    removed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ContactCampaignHistoryResponse(BaseModel):
    """Contact campaign history with removal tracking."""
    contact_id: UUID
    contact_name: str
    contact_email: Optional[str]
    total_campaigns: int
    active_campaigns: int
    removed_campaigns: int
    campaigns: List[CampaignHistoryItem] = []

    model_config = {"from_attributes": True}

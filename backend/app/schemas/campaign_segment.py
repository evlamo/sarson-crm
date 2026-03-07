"""Pydantic schemas for Campaign Segments (called "Lists" in the UI)."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class CampaignSegmentFilters(BaseModel):
    statuses: List[str] = []
    tag_ids: List[UUID] = []
    company_ids: List[UUID] = []


class CampaignSegmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    filters: CampaignSegmentFilters = Field(default_factory=CampaignSegmentFilters)
    contact_ids: List[UUID] = []


class CampaignSegmentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    filters: Optional[CampaignSegmentFilters] = None
    contact_ids: Optional[List[UUID]] = None


class CampaignSegmentResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    filters: dict
    contact_ids: List[UUID]
    mc_segment_id: Optional[int] = None
    mc_synced_at: Optional[datetime] = None
    member_count: int = 0
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CampaignSegmentPreviewResponse(BaseModel):
    count: int
    sample_contacts: List[dict]


class CombinePreviewRequest(BaseModel):
    segment_ids: List[UUID]


class CombineSyncRequest(BaseModel):
    segment_ids: List[UUID]
    campaign_name: str = "Combined Segment"

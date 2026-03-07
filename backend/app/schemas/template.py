"""Pydantic schemas for email templates."""
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel


class TemplateCreate(BaseModel):
    name: str
    subject: Optional[str] = None
    body_html: str
    body_text: Optional[str] = None
    category: Optional[str] = None  # newsletter, outreach, event, lp_update


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    category: Optional[str] = None


class TemplateOut(BaseModel):
    id: UUID
    name: str
    subject: Optional[str]
    body_html: str
    body_text: Optional[str]
    category: Optional[str]
    thumbnail: Optional[str]
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TemplateListOut(BaseModel):
    data: List[TemplateOut]
    total: int
    page: int
    per_page: int


class TemplatePreview(BaseModel):
    """Preview a template with sample contact data merged in."""
    subject: str
    body_html: str
    body_text: Optional[str]


class MergeFieldsRequest(BaseModel):
    """Request to preview template with specific contact data."""
    contact_id: Optional[UUID] = None
    sample_data: Optional[dict] = None  # Override merge fields manually

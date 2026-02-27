from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any
from datetime import datetime, date
from decimal import Decimal
import uuid

from app.schemas.tag import TagResponse


class ContactBase(BaseModel):
    first_name: Optional[str] = Field(None, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    email_secondary: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    phone_secondary: Optional[str] = Field(None, max_length=50)
    title: Optional[str] = Field(None, max_length=200)
    company: Optional[str] = Field(None, max_length=255)
    company_id: Optional[uuid.UUID] = None
    department: Optional[str] = Field(None, max_length=200)
    profile_url: Optional[str] = Field(None, max_length=500)
    linkedin_url: Optional[str] = Field(None, max_length=500)
    website: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    timezone: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = Field(None, max_length=50)
    contact_type: Optional[str] = Field(None, max_length=50)
    lead_source: Optional[str] = Field(None, max_length=100)
    contacted: Optional[bool] = None
    sarson_rep: Optional[str] = Field(None, max_length=255)
    sales_rep: Optional[str] = Field(None, max_length=255)
    assigned_to: Optional[uuid.UUID] = None
    owner_id: Optional[uuid.UUID] = None
    next_step: Optional[str] = Field(None, max_length=2000)
    follow_up_date: Optional[date] = None
    last_contacted_at: Optional[datetime] = None
    last_emailed_at: Optional[datetime] = None
    email_open_count: Optional[int] = Field(None, ge=0)
    email_click_count: Optional[int] = Field(None, ge=0)
    email_valid: Optional[bool] = None
    email_bounced: Optional[bool] = None
    email_unsubscribed: Optional[bool] = None
    unsubscribed_at: Optional[datetime] = None
    commitment_amount: Optional[Decimal] = None
    commitment_currency: Optional[str] = Field(None, max_length=10)
    investor_tier: Optional[str] = Field(None, max_length=50)
    fund_interest: Optional[List[str]] = None
    accredited_status: Optional[bool] = None
    kyc_completed: Optional[bool] = None
    kyc_completed_at: Optional[datetime] = None
    custom_fields: Optional[dict] = None
    notes: Optional[str] = Field(None, max_length=10000)
    source: Optional[str] = Field(None, max_length=100)


class ContactCreate(ContactBase):
    pass


class ContactUpdate(ContactBase):
    """Full update — same as base (all optional for PUT flexibility)."""
    pass


class ContactPatch(BaseModel):
    """Partial update — all fields optional."""
    first_name: Optional[str] = Field(None, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    email_secondary: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    phone_secondary: Optional[str] = Field(None, max_length=50)
    title: Optional[str] = Field(None, max_length=200)
    company: Optional[str] = Field(None, max_length=255)
    company_id: Optional[uuid.UUID] = None
    department: Optional[str] = Field(None, max_length=200)
    profile_url: Optional[str] = Field(None, max_length=500)
    linkedin_url: Optional[str] = Field(None, max_length=500)
    website: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    timezone: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = Field(None, max_length=50)
    contact_type: Optional[str] = Field(None, max_length=50)
    lead_source: Optional[str] = Field(None, max_length=100)
    contacted: Optional[bool] = None
    sarson_rep: Optional[str] = Field(None, max_length=255)
    sales_rep: Optional[str] = Field(None, max_length=255)
    assigned_to: Optional[uuid.UUID] = None
    owner_id: Optional[uuid.UUID] = None
    next_step: Optional[str] = Field(None, max_length=2000)
    follow_up_date: Optional[date] = None
    last_contacted_at: Optional[datetime] = None
    last_emailed_at: Optional[datetime] = None
    email_open_count: Optional[int] = Field(None, ge=0)
    email_click_count: Optional[int] = Field(None, ge=0)
    email_valid: Optional[bool] = None
    email_bounced: Optional[bool] = None
    email_unsubscribed: Optional[bool] = None
    unsubscribed_at: Optional[datetime] = None
    commitment_amount: Optional[Decimal] = None
    commitment_currency: Optional[str] = Field(None, max_length=10)
    investor_tier: Optional[str] = Field(None, max_length=50)
    fund_interest: Optional[List[str]] = None
    accredited_status: Optional[bool] = None
    kyc_completed: Optional[bool] = None
    kyc_completed_at: Optional[datetime] = None
    custom_fields: Optional[dict] = None
    notes: Optional[str] = Field(None, max_length=10000)
    source: Optional[str] = Field(None, max_length=100)


class ContactResponse(ContactBase):
    id: uuid.UUID
    email_domain: Optional[str] = None
    full_name: str = ""
    company_name: Optional[str] = None   # from Company.name if company_id set
    tags: List[TagResponse] = []
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PaginatedContacts(BaseModel):
    data: List[ContactResponse]
    total: int
    page: int
    per_page: int


class BulkUpdateRequest(BaseModel):
    ids: List[uuid.UUID] = Field(..., min_length=1, max_length=500)
    status: Optional[str] = Field(None, max_length=50)
    assigned_to: Optional[uuid.UUID] = None
    tag_ids: Optional[List[uuid.UUID]] = None  # tags to add


class BulkUpdateResponse(BaseModel):
    updated: int
    tags_added: int

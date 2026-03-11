from pydantic import BaseModel, EmailStr, Field, model_validator, field_validator
from typing import Optional, List, Any
from datetime import datetime, date
from decimal import Decimal
import uuid
import re

from app.schemas.tag import TagResponse


class ContactBase(BaseModel):
    first_name: Optional[str] = Field(None, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    email_secondary: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    phone_secondary: Optional[str] = Field(None, max_length=50)

    @field_validator('phone', 'phone_secondary', mode='before')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone format: 10-15 digits with optional + and formatting chars."""
        if not v:
            return v
        # Remove common formatting characters
        cleaned = re.sub(r'[\s\-\(\).]', '', str(v))
        # Ensure it's a valid phone: optional +, then 10-15 digits
        if not re.match(r'^\+?\d{10,15}$', cleaned):
            raise ValueError('Invalid phone format. Expected 10-15 digits (with optional +)')
        return v
    title: Optional[str] = Field(None, max_length=200)
    company: Optional[str] = Field(None, max_length=255)
    company_id: Optional[uuid.UUID] = None
    department: Optional[str] = Field(None, max_length=200)
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
    assigned_to: Optional[uuid.UUID] = None
    owner_id: Optional[uuid.UUID] = None
    next_step: Optional[str] = Field(None, max_length=2000)
    contact_method_preference: Optional[str] = Field(None, max_length=50)
    contact_method_custom: Optional[str] = Field(None, max_length=255)
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
    email: Optional[EmailStr] = None
    email_secondary: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    phone_secondary: Optional[str] = Field(None, max_length=50)
    title: Optional[str] = Field(None, max_length=200)
    company: Optional[str] = Field(None, max_length=255)
    company_id: Optional[uuid.UUID] = None
    department: Optional[str] = Field(None, max_length=200)
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
    assigned_to: Optional[uuid.UUID] = None
    owner_id: Optional[uuid.UUID] = None
    next_step: Optional[str] = Field(None, max_length=2000)
    contact_method_preference: Optional[str] = Field(None, max_length=50)
    contact_method_custom: Optional[str] = Field(None, max_length=255)
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
    # Expose lead_source as 'source' for frontend compatibility
    source: Optional[str] = None

    @model_validator(mode='after')
    def populate_source(self) -> 'ContactResponse':
        # If source wasn't set but lead_source exists on the model, copy it over
        if not self.source and hasattr(self, 'lead_source') and self.lead_source:
            self.source = self.lead_source
        return self

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

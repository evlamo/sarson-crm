from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Any
from datetime import datetime
import uuid


class CompanyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    domain: Optional[str] = Field(None, max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    company_type: Optional[str] = Field(None, max_length=50)
    website: Optional[str] = Field(None, max_length=500)
    linkedin_url: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    employee_count: Optional[int] = Field(None, ge=0)
    revenue_range: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    custom_fields: Optional[dict] = None
    notes: Optional[str] = Field(None, max_length=10000)
    poc_contact_id: Optional[uuid.UUID] = None
    owner_id: Optional[uuid.UUID] = None


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    domain: Optional[str] = Field(None, max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    company_type: Optional[str] = Field(None, max_length=50)
    website: Optional[str] = Field(None, max_length=500)
    linkedin_url: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    employee_count: Optional[int] = Field(None, ge=0)
    revenue_range: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    notes: Optional[str] = Field(None, max_length=10000)
    custom_fields: Optional[dict] = None
    owner_id: Optional[uuid.UUID] = None


class CompanyPatch(BaseModel):
    """Partial update — all fields optional.
    poc_contact_id is intentionally excluded — POC is set via contact status changes only.
    """
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    domain: Optional[str] = Field(None, max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    company_type: Optional[str] = Field(None, max_length=50)
    website: Optional[str] = Field(None, max_length=500)
    linkedin_url: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    employee_count: Optional[int] = Field(None, ge=0)
    revenue_range: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    notes: Optional[str] = Field(None, max_length=10000)
    custom_fields: Optional[dict] = None
    owner_id: Optional[uuid.UUID] = None


class CompanyResponse(CompanyBase):
    id: uuid.UUID
    contact_count: Optional[int] = 0
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PaginatedCompanies(BaseModel):
    data: list[CompanyResponse]
    total: int
    page: int
    per_page: int

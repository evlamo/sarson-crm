from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime


class EmailTemplateCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    design_json: Dict[str, Any]
    html: str
    thumbnail_url: Optional[str] = None


class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    design_json: Optional[Dict[str, Any]] = None
    html: Optional[str] = None
    thumbnail_url: Optional[str] = None


class EmailTemplateResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    design_json: Dict[str, Any]
    html: str
    thumbnail_url: Optional[str]
    is_mailchimp_template: bool
    mailchimp_template_id: Optional[int]
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class MailchimpTemplateImport(BaseModel):
    mailchimp_template_id: int
    name: str

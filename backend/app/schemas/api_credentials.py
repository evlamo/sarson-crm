from datetime import datetime
from typing import Optional, Dict
from uuid import UUID
from pydantic import BaseModel


class MailchimpCredentialsUpdate(BaseModel):
    api_key: Optional[str] = None
    server_prefix: Optional[str] = None
    audience_id: Optional[str] = None
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    webhook_secret: Optional[str] = None


class ApiCredentialsResponse(BaseModel):
    id: UUID
    provider: str
    is_configured: bool
    last_tested_at: Optional[datetime]
    last_test_status: Optional[str]
    last_test_message: Optional[str]
    updated_at: datetime
    masked_fields: Dict[str, str] = {}

    class Config:
        from_attributes = True


class ApiCredentialsTestResponse(BaseModel):
    provider: str
    success: bool
    message: str
    detail: Optional[str] = None

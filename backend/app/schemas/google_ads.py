"""Google Ads OCT schemas."""
import re
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
import uuid


# ── Conversion Actions ─────────────────────────────────────────────────────

class ConversionActionCreate(BaseModel):
    name: str = Field(..., max_length=200)
    google_conversion_action_id: Optional[str] = None
    default_value: float = 0
    trigger_on_status: Optional[str] = None
    is_active: bool = True


class ConversionActionUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    google_conversion_action_id: Optional[str] = None
    default_value: Optional[float] = None
    trigger_on_status: Optional[str] = None
    is_active: Optional[bool] = None


class ConversionActionOut(BaseModel):
    id: str
    name: str
    google_conversion_action_id: Optional[str] = None
    default_value: float
    trigger_on_status: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Manual Conversion ──────────────────────────────────────────────────────

class ManualConversionRequest(BaseModel):
    conversion_name: str
    conversion_value: Optional[float] = None


# ── Sync History ───────────────────────────────────────────────────────────

class ConversionSyncHistoryOut(BaseModel):
    id: str
    contact_id: Optional[str] = None
    gclid: str
    conversion_name: str
    conversion_value: Optional[float] = None
    conversion_time: datetime
    sync_status: str
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    retry_count: int
    synced_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── GCLID Capture ─────────────────────────────────────────────────────────

class ContactGCLIDCapture(BaseModel):
    email: Optional[str] = None
    contact_id: Optional[str] = None
    gclid: str = Field(..., min_length=20, max_length=250)

    @field_validator("gclid")
    @classmethod
    def validate_gclid(cls, v: str) -> str:
        if not re.match(r'^[A-Za-z0-9_\-]{20,250}$', v):
            raise ValueError("Invalid GCLID format — must be 20-250 alphanumeric characters")
        return v


# ── Snippet Config ─────────────────────────────────────────────────────────

class SnippetConfigRequest(BaseModel):
    hidden_field_id: str = "gclid_field"
    cookie_name: str = "_sarson_gclid"


# ── Stats ──────────────────────────────────────────────────────────────────

class GoogleAdsStatsOut(BaseModel):
    synced_today: int
    pending: int
    errors: int
    total_all_time: int

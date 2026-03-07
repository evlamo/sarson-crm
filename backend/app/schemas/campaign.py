"""Pydantic schemas for email campaigns."""
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


# ── Campaign Schemas ──────────────────────────────────────────────────────

class CampaignCreate(BaseModel):
    name: str
    subject: str
    preview_text: Optional[str] = None
    body_html: str
    body_text: Optional[str] = None
    template_id: Optional[UUID] = None
    segment_id: Optional[UUID] = None
    from_name: str = "Sarson Funds"
    from_email: str
    reply_to: Optional[str] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    preview_text: Optional[str] = None
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    template_id: Optional[UUID] = None
    segment_id: Optional[UUID] = None
    from_name: Optional[str] = None
    from_email: Optional[str] = None
    reply_to: Optional[str] = None


class CampaignOut(BaseModel):
    id: UUID
    name: str
    subject: str
    preview_text: Optional[str]
    body_html: str
    body_text: Optional[str]
    template_id: Optional[UUID]
    segment_id: Optional[UUID]
    from_name: str
    from_email: str
    reply_to: Optional[str]
    status: str
    recipient_count: int
    scheduled_at: Optional[datetime]
    sent_at: Optional[datetime]
    sendgrid_batch_id: Optional[str]
    mailchimp_campaign_id: Optional[str] = None
    mailchimp_audience_id: Optional[str] = None
    mailchimp_status: Optional[str] = None
    mc_segment_id_combined: Optional[int] = None
    segment_ids: Optional[List[UUID]] = []
    # Aggregate stats
    sent_count: int
    delivered_count: int
    open_count: int
    unique_opens: int
    click_count: int
    unique_clicks: int
    bounce_count: int
    unsubscribe_count: int
    spam_count: int
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CampaignStats(BaseModel):
    campaign_id: UUID
    name: str
    status: str
    recipient_count: int
    sent_count: int
    delivered_count: int
    open_count: int
    unique_opens: int
    click_count: int
    unique_clicks: int
    bounce_count: int
    unsubscribe_count: int
    spam_count: int
    # Calculated rates
    delivery_rate: float
    open_rate: float
    click_rate: float
    bounce_rate: float
    unsubscribe_rate: float


class EmailSendOut(BaseModel):
    id: UUID
    campaign_id: UUID
    contact_id: UUID
    email_address: str
    message_id: Optional[str]
    status: str
    delivered_at: Optional[datetime]
    first_opened_at: Optional[datetime]
    last_opened_at: Optional[datetime]
    open_count: int
    first_clicked_at: Optional[datetime]
    click_count: int
    bounced_at: Optional[datetime]
    bounce_type: Optional[str]
    unsubscribed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class CampaignSchedule(BaseModel):
    scheduled_at: datetime


class CampaignListOut(BaseModel):
    data: List[CampaignOut]
    total: int
    page: int
    per_page: int


class RecipientListOut(BaseModel):
    data: List[EmailSendOut]
    total: int
    page: int
    per_page: int


class TestSendRequest(BaseModel):
    test_emails: List[str]
    send_type: str = "html"  # "html" or "plaintext"


class MailchimpScheduleRequest(BaseModel):
    schedule_time: str  # ISO 8601, e.g. "2026-03-01T14:00:00+00:00"


class MailchimpSyncRequest(BaseModel):
    contact_ids: Optional[List[str]] = None
    segment_id: Optional[str] = None
    tag_ids: Optional[List[str]] = None
    campaign_list_ids: Optional[List[UUID]] = None  # CRM campaign list IDs (static segments)
    tracking_opens: bool = True
    tracking_html_clicks: bool = True
    google_analytics_tag: str = ""
    timewarp: bool = False

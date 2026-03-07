"""
CRM Campaign Segment (called "List" in the frontend UI).
A named group of contacts used as recipients for email campaigns.
Syncs to Mailchimp as a static segment.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from app.database import Base


class CampaignSegment(Base):
    __tablename__ = "campaign_segments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Filter definition — JSON object with optional keys:
    # { "statuses": [...], "tag_ids": [...], "company_ids": [...] }
    filters = Column(JSONB, default=dict)

    # Manual contact UUID overrides
    contact_ids = Column(ARRAY(UUID(as_uuid=True)), default=list)

    # Mailchimp sync state
    mc_segment_id = Column(Integer, nullable=True)
    mc_synced_at = Column(DateTime(timezone=True), nullable=True)
    member_count = Column(Integer, default=0)

    # Metadata
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

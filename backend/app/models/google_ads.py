"""
Google Ads OCT models — ConversionSyncHistory and ConversionAction.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Numeric, Integer, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class ConversionSyncHistory(Base):
    __tablename__ = "conversion_sync_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_id = Column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)
    gclid = Column(String(250), nullable=False)
    conversion_name = Column(String(200), nullable=False)
    conversion_value = Column(Numeric(10, 2), nullable=True)
    conversion_time = Column(DateTime(timezone=True), nullable=False)
    hashed_email = Column(Text, nullable=True)
    sync_status = Column(String(50), nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    error_code = Column(String(100), nullable=True)
    retry_count = Column(Integer, default=0)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    google_response = Column(JSONB, nullable=True)
    synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class GoogleAdsConversionAction(Base):
    __tablename__ = "google_ads_conversion_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False, unique=True)
    google_conversion_action_id = Column(String(100), nullable=True)
    default_value = Column(Numeric(10, 2), default=0)
    trigger_on_status = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

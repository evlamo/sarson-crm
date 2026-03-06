"""
Campaign Contact Removal Model - Track removal history with reasons
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class CampaignContactRemoval(Base):
    """
    Tracks when a contact is removed from a campaign and the reason.
    Composite unique constraint: (campaign_id, contact_id) - one removal per contact per campaign
    """
    __tablename__ = "campaign_contact_removal"
    __table_args__ = (
        UniqueConstraint("campaign_id", "contact_id", name="uq_campaign_contact_removal"),
        Index("idx_campaign_removal_campaign", "campaign_id"),
        Index("idx_campaign_removal_contact", "contact_id"),
        Index("idx_campaign_removal_removed_at", "removed_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("sales_campaigns.id", ondelete="CASCADE"), nullable=False)
    contact_id = Column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    reason = Column(String(500), nullable=False)  # User-provided reason for removal
    removed_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    removed_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    campaign = relationship("SalesCampaign")
    contact = relationship("Contact")
    removed_by = relationship("User")

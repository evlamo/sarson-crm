"""Campaign Contact Removal tracking model

Tracks when and why a contact is removed from a campaign.
Used for compliance, audit trails, and campaign analytics.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class CampaignContactRemoval(Base):
    """
    Tracks removal of contacts from campaigns.
    One record per contact per campaign.
    """
    __tablename__ = "campaign_contact_removal"
    __table_args__ = (
        UniqueConstraint("contact_id", "sales_campaign_id", name="uq_campaign_contact_removal"),
        Index("idx_campaign_contact_removal_contact", "contact_id"),
        Index("idx_campaign_contact_removal_campaign", "sales_campaign_id"),
        Index("idx_campaign_contact_removal_reason", "reason"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # FK References
    contact_id = Column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    sales_campaign_id = Column(UUID(as_uuid=True), ForeignKey("sales_campaigns.id", ondelete="CASCADE"), nullable=False)
    removed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Removal metadata
    reason = Column(String(50), nullable=False)  # "dnc", "completed", "no_response", "invalid_email"
    notes = Column(Text)  # Optional additional context
    removed_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    
    # Relationships
    contact = relationship("Contact", back_populates="campaign_removals", foreign_keys=[contact_id])
    sales_campaign = relationship("SalesCampaign", foreign_keys=[sales_campaign_id])
    removed_by_user = relationship("User", foreign_keys=[removed_by])

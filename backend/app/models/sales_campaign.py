"""
Sales Campaign and Campaign Contacts models.
Phase 1 Foundation — Campaign hierarchy for managing outreach efforts.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class SalesCampaign(Base):
    """
    A high-level sales campaign that can contain multiple email campaigns.
    Represents a sales initiative, product launch, or outreach effort.
    """
    __tablename__ = "sales_campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(50), default="active")  # active, paused, completed, archived
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])
    email_campaigns = relationship("EmailCampaign", back_populates="sales_campaign")
    campaign_contacts = relationship("CampaignContact", back_populates="sales_campaign", cascade="all, delete-orphan")


class CampaignContact(Base):
    """
    Junction table linking contacts to sales/email campaigns.
    Tracks per-contact status within a campaign.
    
    Key behaviors:
    - One record per contact per sales campaign (enforced by unique constraint)
    - completion_status of 'complete' or 'no' excludes contact from future emails in THIS campaign only
    - excluded_reason documents why contact was removed (dnc, campaign_complete, etc.)
    """
    __tablename__ = "campaign_contacts"
    __table_args__ = (
        UniqueConstraint("contact_id", "sales_campaign_id", name="uq_campaign_contacts_contact_sales"),
        Index("idx_campaign_contacts_contact", "contact_id"),
        Index("idx_campaign_contacts_sales", "sales_campaign_id"),
        Index("idx_campaign_contacts_email", "email_campaign_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_id = Column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    sales_campaign_id = Column(UUID(as_uuid=True), ForeignKey("sales_campaigns.id", ondelete="CASCADE"))
    email_campaign_id = Column(UUID(as_uuid=True), ForeignKey("email_campaigns.id", ondelete="CASCADE"))
    status = Column(String(50), default="active")  # active, complete, no, excluded
    completion_status = Column(String(50))  # NULL, 'complete', 'no'
    excluded_reason = Column(String(255))  # 'dnc', 'campaign_complete', 'campaign_no', 'manual'
    added_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    # Relationships
    contact = relationship("Contact", foreign_keys=[contact_id])
    sales_campaign = relationship("SalesCampaign", back_populates="campaign_contacts")
    email_campaign = relationship("EmailCampaign", foreign_keys=[email_campaign_id])

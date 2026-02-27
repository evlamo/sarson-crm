import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class Activity(Base):
    __tablename__ = "activities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activity_type = Column(String, nullable=False, index=True)
    # note | email_sent | email_received | call | meeting |
    # email_opened | email_clicked | task | status_change

    contact_id = Column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    deal_id = Column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), index=True)

    subject = Column(String)
    body = Column(Text)

    email_campaign_id = Column(UUID(as_uuid=True), ForeignKey("email_campaigns.id", ondelete="SET NULL"))
    email_message_id = Column(String)

    duration_minutes = Column(Integer)
    direction = Column(String)  # inbound | outbound
    outcome = Column(String)

    due_date = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    performed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    performed_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    source = Column(String, default="manual")
    metadata_ = Column("metadata", JSONB, default=dict)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    contact = relationship("Contact", back_populates="activities")
    company = relationship("Company")
    deal = relationship("Deal", back_populates="activities")
    performed_by_user = relationship("User", back_populates="activities", foreign_keys=[performed_by])
    assigned_user = relationship("User", foreign_keys=[assigned_to])
    campaign = relationship("EmailCampaign", foreign_keys=[email_campaign_id])

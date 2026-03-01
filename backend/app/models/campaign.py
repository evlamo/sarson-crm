import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Boolean, Numeric, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    subject = Column(String)
    body_html = Column(Text, nullable=False)
    body_text = Column(Text)
    category = Column(String)
    thumbnail = Column(String)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class EmailCampaign(Base):
    __tablename__ = "email_campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    preview_text = Column(String)
    body_html = Column(Text, nullable=False)
    body_text = Column(Text)
    template_id = Column(UUID(as_uuid=True), ForeignKey("email_templates.id", ondelete="SET NULL"))
    segment_id = Column(UUID(as_uuid=True), ForeignKey("segments.id", ondelete="SET NULL"))
    filter_snapshot = Column(JSONB)
    recipient_count = Column(Integer, default=0)
    from_name = Column(String, nullable=False, default="Speranza CRM")
    from_email = Column(String, nullable=False, server_default="info@sarsonfunds.com")
    reply_to = Column(String)
    status = Column(String, default="draft", index=True)
    scheduled_at = Column(DateTime(timezone=True))
    sent_at = Column(DateTime(timezone=True))
    sendgrid_batch_id = Column(String)

    # Mailchimp integration
    mailchimp_campaign_id = Column(String)
    mailchimp_audience_id = Column(String)
    mailchimp_status = Column(String)  # draft/scheduled/sending/sent
    mailchimp_segment_tag = Column(String, nullable=True)

    # Campaign Lists (static segments)
    segment_ids = Column(ARRAY(UUID(as_uuid=True)), default=list)
    mc_segment_id_combined = Column(Integer, nullable=True)

    # Aggregate stats
    sent_count = Column(Integer, default=0)
    delivered_count = Column(Integer, default=0)
    open_count = Column(Integer, default=0)
    unique_opens = Column(Integer, default=0)
    click_count = Column(Integer, default=0)
    unique_clicks = Column(Integer, default=0)
    bounce_count = Column(Integer, default=0)
    unsubscribe_count = Column(Integer, default=0)
    spam_count = Column(Integer, default=0)

    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    sends = relationship("EmailSend", back_populates="campaign", cascade="all, delete-orphan")
    segment = relationship("Segment", foreign_keys=[segment_id])


class EmailSend(Base):
    __tablename__ = "email_sends"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("email_campaigns.id", ondelete="CASCADE"), index=True)
    contact_id = Column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    email_address = Column(String, nullable=False)
    message_id = Column(String, unique=True)
    status = Column(String, default="queued", index=True)
    delivered_at = Column(DateTime(timezone=True))
    first_opened_at = Column(DateTime(timezone=True))
    last_opened_at = Column(DateTime(timezone=True))
    open_count = Column(Integer, default=0)
    first_clicked_at = Column(DateTime(timezone=True))
    click_count = Column(Integer, default=0)
    bounced_at = Column(DateTime(timezone=True))
    bounce_type = Column(String)
    unsubscribed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    campaign = relationship("EmailCampaign", back_populates="sends")
    contact = relationship("Contact", back_populates="email_sends")

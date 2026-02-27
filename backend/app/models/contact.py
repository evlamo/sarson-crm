import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, Numeric, DateTime, ForeignKey, Text, ARRAY, Date, event
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR
from sqlalchemy.orm import relationship
from app.database import Base

class Contact(Base):
    __tablename__ = "contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identity
    first_name = Column(String)
    middle_name = Column(Text)
    last_name = Column(String)
    email = Column(String, index=True)
    email_secondary = Column(String)
    phone = Column(String)
    phone_secondary = Column(String)

    # Professional
    title = Column(String)
    company = Column(String, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), index=True)
    department = Column(String)
    linkedin_url = Column(String)
    website = Column(String)
    email_domain = Column(Text)       # stored for fast firm-level filtering
    profile_url = Column(Text)        # LinkedIn, AngelList, etc.
    sarson_rep = Column(Text)         # Sarson Funds representative name
    sales_rep = Column(Text)          # External sales person

    # Location
    city = Column(String)
    state = Column(String)
    country = Column(String, default="US")
    timezone = Column(String)

    # CRM
    contact_type = Column(String, default="prospect", index=True)
    status = Column(String, default="active", index=True)
    lead_source = Column(String)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    next_step = Column(Text)          # free-text next action
    follow_up_date = Column(Date)     # scheduled follow-up date
    contacted = Column(Boolean, default=False)  # has this person officially spoken with the firm?

    # Engagement
    last_contacted_at = Column(DateTime(timezone=True))
    last_emailed_at = Column(DateTime(timezone=True))
    email_open_count = Column(Integer, default=0)
    email_click_count = Column(Integer, default=0)

    # Email deliverability
    email_valid = Column(Boolean, default=True)
    email_bounced = Column(Boolean, default=False)
    email_unsubscribed = Column(Boolean, default=False)
    unsubscribed_at = Column(DateTime(timezone=True))

    # Investment-specific
    commitment_amount = Column(Numeric(15, 2))
    commitment_currency = Column(String, default="USD")
    investor_tier = Column(String)
    fund_interest = Column(ARRAY(String))
    accredited_status = Column(Boolean)
    kyc_completed = Column(Boolean, default=False)
    kyc_completed_at = Column(DateTime(timezone=True))

    # Full-text search vector (auto-updated by DB trigger)
    search_vector = Column(TSVECTOR)

    # Meta
    custom_fields = Column(JSONB, default=dict)
    notes = Column(Text)
    source_import_id = Column(String)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    deleted_at = Column(DateTime(timezone=True))

    # Relationships
    owner = relationship("User", back_populates="owned_contacts", foreign_keys=[owner_id])
    company_obj = relationship("Company", back_populates="contacts")
    tags = relationship("Tag", secondary="contact_tags", back_populates="contacts")
    activities = relationship("Activity", back_populates="contact", cascade="all, delete-orphan")
    deal_contacts = relationship("DealContact", back_populates="contact")
    email_sends = relationship("EmailSend", back_populates="contact")

    @property
    def full_name(self):
        parts = [self.first_name or "", self.last_name or ""]
        return " ".join(p for p in parts if p).strip() or self.email or "Unknown"


def _extract_email_domain(target, value, oldvalue, initiator):
    """Auto-populate email_domain from email on set."""
    if value and "@" in value:
        target.email_domain = value.split("@", 1)[1].lower()
    else:
        target.email_domain = None


event.listen(Contact.email, "set", _extract_email_domain)

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Integer, Numeric, DateTime, ForeignKey, Text, ARRAY, Date, event, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from app.database import Base
from app.services.encryption_service import encrypt_email, decrypt_email

def _utcnow():
    return datetime.now(timezone.utc)

class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (
        # Partial unique index on encrypted email — allows multiple nulls, but no duplicate non-null emails
        # GIN index for full-text search
        Index("ix_contacts_search_vector", "search_vector", postgresql_using="gin"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identity
    first_name = Column(String)
    middle_name = Column(Text)
    last_name = Column(String)
    _email_encrypted = Column("email", String, index=True)  # Encrypted email stored in DB
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
    sarson_rep = Column(Text, index=True)  # Sarson Funds representative name
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
    contact_method_preference = Column(String(50))   # phone, email, text, whatsapp, telegram, linkedin, other
    contact_method_custom = Column(String(255))       # free-text when preference == 'other'
    last_contacted_at = Column(DateTime(timezone=True), index=True)
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

    # Google Ads OCT
    gclid = Column(String(250))
    gclid_captured_at = Column(DateTime(timezone=True))
    gclid_expires_at = Column(DateTime(timezone=True))
    conversion_synced = Column(Boolean, default=False)
    conversion_synced_at = Column(DateTime(timezone=True))
    conversion_name = Column(String(200))
    conversion_value = Column(Numeric(10, 2))
    conversion_status = Column(String(50))

    # Full-text search vector (auto-updated by DB trigger)
    search_vector = Column(TSVECTOR)

    # Meta
    custom_fields = Column(JSONB, default=dict)
    notes = Column(Text)
    source_import_id = Column(String)

    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    deleted_at = Column(DateTime(timezone=True))

    # Relationships
    owner = relationship("User", back_populates="owned_contacts", foreign_keys=[owner_id])
    company_obj = relationship("Company", back_populates="contacts", foreign_keys="Contact.company_id")
    tags = relationship("Tag", secondary="contact_tags", back_populates="contacts")
    activities = relationship("Activity", back_populates="contact", cascade="all, delete-orphan")
    deal_contacts = relationship("DealContact", back_populates="contact")
    email_sends = relationship("EmailSend", back_populates="contact")
    campaign_removals = relationship("CampaignContactRemoval", back_populates="contact", cascade="all, delete-orphan")

    @hybrid_property
    def email(self):
        """Get decrypted email."""
        if self._email_encrypted:
            return decrypt_email(self._email_encrypted)
        return None

    @email.setter
    def email(self, value):
        """Set email (encrypts before storage)."""
        if value:
            self._email_encrypted = encrypt_email(value)
            # Also update email_domain from plaintext value
            if "@" in value:
                self.email_domain = value.split("@", 1)[1].lower()
        else:
            self._email_encrypted = None
            self.email_domain = None

    @property
    def full_name(self):
        parts = [self.first_name or "", self.last_name or ""]
        return " ".join(p for p in parts if p).strip() or self.email or "Unknown"


def _extract_email_domain(target, value, oldvalue, initiator):
    """Auto-populate email_domain from encrypted email on set."""
    # Since email setter handles this, this listener is now a fallback for direct DB updates
    if value and "@" in value:
        target.email_domain = value.split("@", 1)[1].lower()
    else:
        target.email_domain = None


event.listen(Contact._email_encrypted, "set", _extract_email_domain)

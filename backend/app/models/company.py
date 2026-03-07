import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base

class Company(Base):
    __tablename__ = "companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, index=True)
    domain = Column(String, unique=True)
    industry = Column(String)
    company_type = Column(String, index=True)  # lp_firm | deal_target | portfolio | service_provider
    website = Column(String)
    linkedin_url = Column(String)
    city = Column(String)
    state = Column(String)
    country = Column(String, default="US")
    employee_count = Column(Integer)
    revenue_range = Column(String)
    description = Column(String)
    custom_fields = Column(JSONB, default=dict)
    notes = Column(Text)
    poc_contact_id = Column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL", use_alter=True))
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime(timezone=True))

    # Relationships
    contacts = relationship("Contact", back_populates="company_obj", foreign_keys="Contact.company_id")
    poc_contact = relationship("Contact", foreign_keys=[poc_contact_id], post_update=True)
    deals = relationship("Deal", back_populates="company")
    owner = relationship("User", foreign_keys=[owner_id])

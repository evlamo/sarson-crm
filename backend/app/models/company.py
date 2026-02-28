import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
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
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime(timezone=True))

    # Relationships
    contacts = relationship("Contact", back_populates="company_obj")
    deals = relationship("Deal", back_populates="company")
    owner = relationship("User", foreign_keys=[owner_id])

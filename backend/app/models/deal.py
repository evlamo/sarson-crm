import uuid
from datetime import datetime
from sqlalchemy import Column, String, Numeric, Date, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class Pipeline(Base):
    __tablename__ = "pipelines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    stages = Column(JSONB, nullable=False)  # [{name, order, probability, color}]
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    deals = relationship("Deal", back_populates="pipeline")


class Deal(Base):
    __tablename__ = "deals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    description = Column(String)
    stage = Column(String, nullable=False, default="sourced", index=True)
    pipeline_id = Column(UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="SET NULL"))
    amount = Column(Numeric(15, 2))
    currency = Column(String, default="USD")
    expected_close = Column(Date)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"))
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    deal_type = Column(String)
    fund_target = Column(String)
    sector = Column(String)
    geography = Column(String)
    win_reason = Column(String)
    loss_reason = Column(String)
    custom_fields = Column(JSONB, default=dict)
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    # Relationships
    company = relationship("Company", back_populates="deals")
    pipeline = relationship("Pipeline", back_populates="deals")
    owner = relationship("User", foreign_keys=[owner_id])
    deal_contacts = relationship("DealContact", back_populates="deal", cascade="all, delete-orphan")
    activities = relationship("Activity", back_populates="deal")


class DealContact(Base):
    __tablename__ = "deal_contacts"

    deal_id = Column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), primary_key=True)
    contact_id = Column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True)
    role = Column(String)

    deal = relationship("Deal", back_populates="deal_contacts")
    contact = relationship("Contact", back_populates="deal_contacts")

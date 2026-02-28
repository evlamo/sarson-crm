import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

StaticListMember = Table(
    "static_list_members",
    Base.metadata,
    Column("list_id", UUID(as_uuid=True), ForeignKey("static_lists.id", ondelete="CASCADE"), primary_key=True),
    Column("contact_id", UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True),
    Column("added_at", DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
)


class StaticList(Base):
    __tablename__ = "static_lists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(Text)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    contacts = relationship("Contact", secondary="static_list_members", lazy="dynamic")
    creator = relationship("User", foreign_keys=[created_by])

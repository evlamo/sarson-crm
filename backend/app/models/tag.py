import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

ContactTag = Table(
    "contact_tags",
    Base.metadata,
    Column("contact_id", UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    Column("added_by", UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")),
    Column("added_at", DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
)

class Tag(Base):
    __tablename__ = "tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True, index=True)
    color = Column(String, default="#e8630a")
    category = Column(String)  # segment | status | fund | custom
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    contacts = relationship("Contact", secondary="contact_tags", back_populates="tags")

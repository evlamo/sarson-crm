import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class ApiCredentials(Base):
    __tablename__ = "api_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String(100), nullable=False, unique=True)
    credentials = Column(JSONB, nullable=False, default=dict)
    is_configured = Column(Boolean, default=False)
    last_tested_at = Column(DateTime(timezone=True), nullable=True)
    last_test_status = Column(String(50), nullable=True)
    last_test_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

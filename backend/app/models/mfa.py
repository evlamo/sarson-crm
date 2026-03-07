import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

class MFASecret(Base):
    __tablename__ = "mfa_secrets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    secret_key = Column(String, nullable=False)  # Encrypted TOTP secret
    is_enabled = Column(Boolean, default=False)
    backup_codes = Column(String, nullable=True)  # Comma-separated encrypted backup codes
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    enabled_at = Column(DateTime(timezone=True), nullable=True)

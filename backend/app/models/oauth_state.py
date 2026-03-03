"""OAuth state model for CSRF protection during OAuth flows."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import Column, String, Text, DateTime
from app.database import Base


def _default_expires() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=10)


class OAuthState(Base):
    __tablename__ = "oauth_states"

    state = Column(String(255), primary_key=True)
    redirect_uri = Column(Text, nullable=True)  # Optional: store intended redirect
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), default=_default_expires)

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

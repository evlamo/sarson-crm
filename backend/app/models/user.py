import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="member")  # admin | member
    avatar_url = Column(String)
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # ========== RBAC PERMISSIONS (Phase 1 Foundation) ==========
    can_manage_users = Column(Boolean, default=False)        # Create/edit/deactivate users
    can_manage_campaigns = Column(Boolean, default=False)    # Create/edit/delete campaigns
    can_approve_imports = Column(Boolean, default=False)     # Review and approve sheet imports
    can_revert_db = Column(Boolean, default=False)           # Restore from snapshots
    can_manage_integrations = Column(Boolean, default=False) # Configure Mailchimp, Sheets, etc.

    # Relationships
    owned_contacts = relationship("Contact", back_populates="owner", foreign_keys="Contact.owner_id")
    activities = relationship("Activity", back_populates="performed_by_user", foreign_keys="Activity.performed_by")

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        if self.is_admin:
            return True
        return getattr(self, permission, False)

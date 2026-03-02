"""
Audit and history models.
Phase 1 Foundation — Full audit trail for compliance and debugging.
Phase 4 — Enhanced with stats-based snapshots + optimized indexes.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, BigInteger, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class AuditLog(Base):
    """
    Global audit log for tracking all user actions.
    Captures who did what, when, and what changed.
    """
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("idx_audit_log_entity", "entity_type", "entity_id"),
        Index("idx_audit_log_user", "user_id"),
        Index("idx_audit_log_action", "action"),
        Index("idx_audit_log_created_at", "created_at"),
        # Composite index for entity + time range queries (common in Activity page)
        Index("idx_audit_log_entity_time", "entity_type", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    action = Column(String(100), nullable=False)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(UUID(as_uuid=True))
    old_values = Column(JSONB)
    new_values = Column(JSONB)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)

    user = relationship("User", foreign_keys=[user_id])


class ContactFieldHistory(Base):
    """
    Granular field-level change history for contacts.
    Enables "show me what changed on this field over time" queries.
    """
    __tablename__ = "contact_field_history"
    __table_args__ = (
        Index("idx_field_history_contact", "contact_id"),
        Index("idx_field_history_contact_field", "contact_id", "field_name"),
        Index("idx_field_history_changed_at", "changed_at"),
        # Composite index for per-contact time-ordered queries
        Index("idx_field_history_contact_time", "contact_id", "changed_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contact_id = Column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text)
    new_value = Column(Text)
    changed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    changed_at = Column(DateTime(timezone=True), default=_utcnow, index=True)
    source = Column(String(50), default="manual")

    contact = relationship("Contact", foreign_keys=[contact_id])
    changed_by_user = relationship("User", foreign_keys=[changed_by])


class DbSnapshot(Base):
    """
    Registry of database snapshots for rollback capability.
    Supports both file-based backups and lightweight stats snapshots.
    """
    __tablename__ = "db_snapshots"
    __table_args__ = (
        Index("idx_db_snapshots_created_at", "created_at"),
        Index("idx_db_snapshots_type", "snapshot_type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    label = Column(String(255))
    snapshot_type = Column(String(50), default="auto")  # 'auto', 'manual', 'pre_import', 'stats'
    file_path = Column(Text)  # nullable for stats-based snapshots
    file_size_bytes = Column(BigInteger)
    data = Column(JSONB)  # For stats-based snapshots: counts, recent changes, etc.
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), default=_utcnow, index=True)
    expires_at = Column(DateTime(timezone=True))

    creator = relationship("User", foreign_keys=[created_by])

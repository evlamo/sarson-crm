"""
Google Sheets sync models.
Phase 1 Foundation — Track exports to Sheets and manage import reviews.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class SheetsExport(Base):
    """
    Registry of Google Sheets exports.
    Tracks which filters were used to generate each sheet export.
    """
    __tablename__ = "sheets_exports"
    __table_args__ = (
        Index("idx_sheets_exports_spreadsheet", "spreadsheet_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    spreadsheet_id = Column(String(255), nullable=False)
    spreadsheet_url = Column(Text)
    sheet_name = Column(String(255))
    filter_criteria = Column(JSONB)  # the filter used to generate this export
    contact_count = Column(Integer)
    exported_at = Column(DateTime(timezone=True), default=_utcnow)
    exported_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    last_synced_at = Column(DateTime(timezone=True))
    sync_status = Column(String(50), default="active")  # active, archived, error

    # Relationships
    exporter = relationship("User", foreign_keys=[exported_by])
    import_reviews = relationship("SheetsImportReview", back_populates="export", cascade="all, delete-orphan")


class SheetsImportReview(Base):
    """
    Pending imports from Google Sheets requiring admin review.
    Captures raw data from sheet and any detected conflicts.
    """
    __tablename__ = "sheets_import_reviews"
    __table_args__ = (
        Index("idx_sheets_import_reviews_export", "export_id"),
        Index("idx_sheets_import_reviews_status", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    export_id = Column(UUID(as_uuid=True), ForeignKey("sheets_exports.id", ondelete="SET NULL"))
    import_data = Column(JSONB, nullable=False)  # the raw data from the sheet
    conflict_data = Column(JSONB)  # conflicts detected during review
    status = Column(String(50), default="pending")  # pending, approved, rejected, partial
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    export = relationship("SheetsExport", back_populates="import_reviews")
    reviewer = relationship("User", foreign_keys=[reviewed_by])

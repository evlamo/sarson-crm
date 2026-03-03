"""
Service for CRM Campaign Segments (Lists).
Handles filter resolution, contact collection, and Mailchimp static segment sync.
"""
import logging
from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.models.campaign_segment import CampaignSegment
from app.models.tag import Tag

logger = logging.getLogger(__name__)


def resolve_segment_contacts(segment: CampaignSegment, db: Session) -> List[Contact]:
    """
    Resolve all contacts for a campaign segment by combining filter-based and manual contacts.
    Deduplicates by contact ID. Excludes deleted, bounced, and unsubscribed contacts.
    """
    filters = segment.filters or {}
    contact_set: dict = {}

    # --- Filter-based contacts ---
    q = db.query(Contact).filter(Contact.deleted_at.is_(None))
    q = q.filter(
        Contact.email_unsubscribed.isnot(True),
        Contact.email_bounced.isnot(True),
        Contact.master_dnc.isnot(True),  # Exclude master DNC contacts
    )

    has_filters = False

    statuses = filters.get("statuses", [])
    if statuses:
        q = q.filter(Contact.status.in_(statuses))
        has_filters = True

    tag_ids = [str(t) for t in filters.get("tag_ids", []) if t]
    if tag_ids:
        from uuid import UUID as PyUUID
        from sqlalchemy import or_ as sa_or_
        tag_uuid_list = [PyUUID(tid) for tid in tag_ids]
        # OR logic: contact has ANY of the selected tags
        q = q.filter(
            sa_or_(*[Contact.tags.any(Tag.id == tid) for tid in tag_uuid_list])
        )
        has_filters = True

    company_ids = filters.get("company_ids", [])
    if company_ids:
        q = q.filter(Contact.company_id.in_(company_ids))
        has_filters = True

    if has_filters:
        for c in q.all():
            if c.email:
                contact_set[c.id] = c

    # --- Manual contact overrides ---
    manual_ids = [str(cid) for cid in (segment.contact_ids or []) if cid]
    if manual_ids:
        manual_contacts = db.query(Contact).filter(
            Contact.id.in_(manual_ids),
            Contact.deleted_at.is_(None),
            Contact.email_unsubscribed.isnot(True),
            Contact.email_bounced.isnot(True),
        ).all()
        for c in manual_contacts:
            if c.email:
                contact_set[c.id] = c

    return list(contact_set.values())


def resolve_combined_segment_contacts(segment_ids: List[UUID], db: Session) -> List[Contact]:
    """Combine contacts from multiple segments (union, deduplicated)."""
    combined: dict = {}
    for seg_id in segment_ids:
        segment = db.query(CampaignSegment).filter(CampaignSegment.id == seg_id).first()
        if segment:
            for c in resolve_segment_contacts(segment, db):
                combined[c.id] = c
    return list(combined.values())


def get_segment_preview(segment: CampaignSegment, db: Session, sample_limit: int = 5) -> dict:
    """Get count and sample contacts for a segment."""
    contacts = resolve_segment_contacts(segment, db)
    sample = contacts[:sample_limit]
    return {
        "count": len(contacts),
        "sample_contacts": [
            {
                "id": str(c.id),
                "first_name": c.first_name or "",
                "last_name": c.last_name or "",
                "email": c.email or "",
                "status": c.status or "",
            }
            for c in sample
        ],
    }

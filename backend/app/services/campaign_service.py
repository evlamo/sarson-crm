"""
Campaign service — recipient resolution, merge field rendering, send preparation.
"""
import re
from typing import List, Dict, Any
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.campaign import EmailCampaign, EmailSend
from app.models.contact import Contact
from app.models.segment import Segment
from app.models.sales_campaign import SalesCampaign
from app.models.campaign_contact_removal import CampaignContactRemoval
from app.services.segment_service import build_segment_query


# ── Merge Field Rendering ──────────────────────────────────────────────────

MERGE_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def render_merge_fields(template: str, contact_data: Dict[str, Any]) -> str:
    """Replace {{field}} merge tags with contact data. Unknown tags become empty string."""
    def replacer(match):
        field = match.group(1)
        return str(contact_data.get(field, ""))
    return MERGE_PATTERN.sub(replacer, template)


# ── Recipient Resolution ──────────────────────────────────────────────────

def resolve_recipients(
    campaign: EmailCampaign,
    db: Session,
) -> List[Dict[str, Any]]:
    """
    Resolve campaign segment → list of valid recipient dicts.
    Filters out: unsubscribed, bounced, invalid email, do_not_contact, no email.
    """
    if campaign.segment_id is None:
        return []

    segment = db.query(Segment).filter(Segment.id == campaign.segment_id).first()
    if not segment:
        return []

    # Use the segment query builder, then add email-safety filters
    query = build_segment_query(db, segment.filters)
    query = query.filter(
        and_(
            Contact.email.isnot(None),
            Contact.email != "",
            Contact.email_unsubscribed.is_(False),
            Contact.email_bounced.is_(False),
            Contact.email_valid.is_(True),
            Contact.status != "do_not_contact",
        )
    ).with_entities(
        Contact.id,
        Contact.email,
        Contact.first_name,
        Contact.last_name,
        Contact.company,
    )

    return [
        {
            "contact_id": row.id,
            "email": row.email,
            "first_name": row.first_name or "",
            "last_name": row.last_name or "",
            "company": row.company or "",
            "full_name": f"{row.first_name or ''} {row.last_name or ''}".strip(),
        }
        for row in query.all()
    ]


# ── Send Preparation ──────────────────────────────────────────────────────

def prepare_send(campaign_id: UUID, db: Session) -> int:
    """
    Create EmailSend records for all valid recipients.
    Returns recipient count. Updates campaign status to 'sending'.
    """
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not campaign:
        raise ValueError(f"Campaign {campaign_id} not found")

    recipients = resolve_recipients(campaign, db)
    if not recipients:
        raise ValueError("No valid recipients found for this campaign")

    # Snapshot the filter at send time
    if campaign.segment_id:
        segment = db.query(Segment).filter(Segment.id == campaign.segment_id).first()
        if segment:
            campaign.filter_snapshot = segment.filters

    # Create EmailSend records in bulk
    send_records = []
    for r in recipients:
        send = EmailSend(
            campaign_id=campaign.id,
            contact_id=r["contact_id"],
            email_address=r["email"],
            status="queued",
        )
        send_records.append(send)

    db.bulk_save_objects(send_records)
    campaign.recipient_count = len(recipients)
    campaign.status = "sending"
    db.commit()

    return len(recipients)


def get_campaign_stats(campaign: EmailCampaign) -> Dict[str, Any]:
    """Calculate campaign analytics with rates."""
    sent = campaign.sent_count or 0
    delivered = campaign.delivered_count or 0

    def safe_rate(numerator: int, denominator: int) -> float:
        return round((numerator / denominator) * 100, 2) if denominator > 0 else 0.0

    return {
        "campaign_id": campaign.id,
        "name": campaign.name,
        "status": campaign.status,
        "recipient_count": campaign.recipient_count or 0,
        "sent_count": sent,
        "delivered_count": delivered,
        "open_count": campaign.open_count or 0,
        "unique_opens": campaign.unique_opens or 0,
        "click_count": campaign.click_count or 0,
        "unique_clicks": campaign.unique_clicks or 0,
        "bounce_count": campaign.bounce_count or 0,
        "unsubscribe_count": campaign.unsubscribe_count or 0,
        "spam_count": campaign.spam_count or 0,
        "delivery_rate": safe_rate(delivered, sent),
        "open_rate": safe_rate(campaign.unique_opens or 0, delivered),
        "click_rate": safe_rate(campaign.unique_clicks or 0, delivered),
        "bounce_rate": safe_rate(campaign.bounce_count or 0, sent),
        "unsubscribe_rate": safe_rate(campaign.unsubscribe_count or 0, delivered),
    }


def remove_contact_from_campaign(
    campaign_id: UUID,
    contact_id: UUID,
    reason: str,
    user_id: UUID,
    db: Session,
) -> CampaignContactRemoval:
    """
    Remove a contact from a sales campaign.
    
    Creates a CampaignContactRemoval record to track the removal.
    Validates that contact exists in the campaign.
    """
    # Validate campaign exists
    campaign = db.query(SalesCampaign).filter(SalesCampaign.id == campaign_id).first()
    if not campaign:
        raise ValueError(f"Campaign {campaign_id} not found")
    
    # Validate contact exists
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise ValueError(f"Contact {contact_id} not found")
    
    # Create removal record
    removal = CampaignContactRemoval(
        contact_id=contact_id,
        sales_campaign_id=campaign_id,
        reason=reason,
        removed_by=user_id,
    )
    
    db.add(removal)
    db.commit()
    db.refresh(removal)
    
    return removal

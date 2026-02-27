"""
SendGrid webhook handler — processes email events (delivered, open, click, bounce, etc.)
Updates email_sends records and contact-level engagement fields.
"""
import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_

from app.database import SessionLocal
from app.models.campaign import EmailCampaign, EmailSend
from app.models.contact import Contact
from app.models.activity import Activity
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


# ── Event Schema ───────────────────────────────────────────────────────────

class SendGridEvent(BaseModel):
    email: str
    timestamp: Optional[int] = None
    event: str  # delivered, open, click, bounce, dropped, deferred, spamreport, unsubscribe
    sg_message_id: Optional[str] = None
    category: Optional[list] = None
    campaign_id: Optional[str] = None
    contact_id: Optional[str] = None
    url: Optional[str] = None  # for click events
    type: Optional[str] = None  # for bounce: "bounce" or "blocked"
    reason: Optional[str] = None
    status: Optional[str] = None


# ── Signature Verification ─────────────────────────────────────────────────

def verify_sendgrid_signature(request_body: bytes, signature: str, timestamp: str) -> bool:
    """Verify SendGrid webhook signature (v3 signed event webhook)."""
    verification_key = settings.sendgrid_api_key
    if not verification_key:
        logger.warning("No SendGrid API key configured — skipping signature verification")
        return True  # Allow in dev mode

    payload = timestamp + request_body.decode("utf-8")
    expected = hmac.new(
        verification_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


# ── Event Handlers ─────────────────────────────────────────────────────────

def _get_event_time(event: SendGridEvent) -> datetime:
    if event.timestamp:
        return datetime.fromtimestamp(event.timestamp, tz=timezone.utc)
    return datetime.now(timezone.utc)


def _find_send_record(db, event: SendGridEvent) -> Optional[EmailSend]:
    """Find EmailSend by sg_message_id or by email + campaign_id."""
    if event.sg_message_id:
        # Strip the filter ID suffix from SendGrid message IDs
        msg_id = event.sg_message_id.split(".")[0] if "." in event.sg_message_id else event.sg_message_id
        record = db.query(EmailSend).filter(EmailSend.message_id == msg_id).first()
        if record:
            return record

    # Fallback: try custom args
    if event.campaign_id and event.email:
        return db.query(EmailSend).filter(
            and_(
                EmailSend.campaign_id == event.campaign_id,
                EmailSend.email_address == event.email,
            )
        ).first()
    return None


def handle_delivered(db, event: SendGridEvent, send: EmailSend):
    event_time = _get_event_time(event)
    send.status = "delivered"
    send.delivered_at = event_time

    # Update campaign aggregate
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == send.campaign_id).first()
    if campaign:
        campaign.delivered_count = (campaign.delivered_count or 0) + 1


def handle_open(db, event: SendGridEvent, send: EmailSend):
    event_time = _get_event_time(event)
    if not send.first_opened_at:
        send.first_opened_at = event_time
        # Count unique opens
        campaign = db.query(EmailCampaign).filter(EmailCampaign.id == send.campaign_id).first()
        if campaign:
            campaign.unique_opens = (campaign.unique_opens or 0) + 1
    send.last_opened_at = event_time
    send.open_count = (send.open_count or 0) + 1

    # Update campaign total opens
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == send.campaign_id).first()
    if campaign:
        campaign.open_count = (campaign.open_count or 0) + 1

    # Update contact engagement
    contact = db.query(Contact).filter(Contact.id == send.contact_id).first()
    if contact:
        contact.email_open_count = (contact.email_open_count or 0) + 1
        contact.last_emailed_at = event_time

    # Log activity
    _log_activity(db, send, "email_opened", f"Opened campaign email")


def handle_click(db, event: SendGridEvent, send: EmailSend):
    event_time = _get_event_time(event)
    if not send.first_clicked_at:
        send.first_clicked_at = event_time
        campaign = db.query(EmailCampaign).filter(EmailCampaign.id == send.campaign_id).first()
        if campaign:
            campaign.unique_clicks = (campaign.unique_clicks or 0) + 1
    send.click_count = (send.click_count or 0) + 1

    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == send.campaign_id).first()
    if campaign:
        campaign.click_count = (campaign.click_count or 0) + 1

    contact = db.query(Contact).filter(Contact.id == send.contact_id).first()
    if contact:
        contact.email_click_count = (contact.email_click_count or 0) + 1

    url = event.url or "unknown"
    _log_activity(db, send, "email_clicked", f"Clicked link: {url}")


def handle_bounce(db, event: SendGridEvent, send: EmailSend):
    event_time = _get_event_time(event)
    send.bounced_at = event_time
    send.status = "bounced"

    # Determine bounce type
    bounce_type = "hard" if event.type == "bounce" else "soft"
    send.bounce_type = bounce_type

    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == send.campaign_id).first()
    if campaign:
        campaign.bounce_count = (campaign.bounce_count or 0) + 1

    # Hard bounce → mark contact email as invalid
    if bounce_type == "hard":
        contact = db.query(Contact).filter(Contact.id == send.contact_id).first()
        if contact:
            contact.email_bounced = True
            contact.email_valid = False

    _log_activity(db, send, "email_bounced", f"Email bounced ({bounce_type}): {event.reason or 'unknown'}")


def handle_unsubscribe(db, event: SendGridEvent, send: EmailSend):
    event_time = _get_event_time(event)
    send.status = "unsubscribed"
    send.unsubscribed_at = event_time

    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == send.campaign_id).first()
    if campaign:
        campaign.unsubscribe_count = (campaign.unsubscribe_count or 0) + 1

    contact = db.query(Contact).filter(Contact.id == send.contact_id).first()
    if contact:
        contact.email_unsubscribed = True
        contact.unsubscribed_at = event_time

    _log_activity(db, send, "email_unsubscribed", "Contact unsubscribed from emails")


def handle_spam_report(db, event: SendGridEvent, send: EmailSend):
    event_time = _get_event_time(event)
    send.status = "spam"

    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == send.campaign_id).first()
    if campaign:
        campaign.spam_count = (campaign.spam_count or 0) + 1

    contact = db.query(Contact).filter(Contact.id == send.contact_id).first()
    if contact:
        contact.email_unsubscribed = True
        contact.unsubscribed_at = event_time
        contact.status = "do_not_contact"

    _log_activity(db, send, "email_spam_report", "Contact reported email as spam")


def handle_dropped(db, event: SendGridEvent, send: EmailSend):
    send.status = "dropped"
    _log_activity(db, send, "email_dropped", f"Email dropped: {event.reason or 'unknown'}")


def handle_deferred(db, event: SendGridEvent, send: EmailSend):
    """Deferred events are retried by SendGrid — just log it."""
    _log_activity(db, send, "email_deferred", f"Email deferred: {event.reason or 'unknown'}")


def _log_activity(db, send: EmailSend, activity_type: str, body: str):
    """Log an email event as a contact activity."""
    activity = Activity(
        activity_type=activity_type,
        contact_id=send.contact_id,
        email_campaign_id=send.campaign_id,
        email_message_id=send.message_id,
        body=body,
        source="email_sync",
    )
    db.add(activity)


# ── Event Handler Map ──────────────────────────────────────────────────────

EVENT_HANDLERS = {
    "delivered": handle_delivered,
    "open": handle_open,
    "click": handle_click,
    "bounce": handle_bounce,
    "blocked": handle_bounce,  # blocked = hard bounce variant
    "unsubscribe": handle_unsubscribe,
    "spamreport": handle_spam_report,
    "dropped": handle_dropped,
    "deferred": handle_deferred,
}


# ── Webhook Endpoint ──────────────────────────────────────────────────────

@router.post("/sendgrid")
async def sendgrid_webhook(request: Request):
    """
    Receives SendGrid Event Webhook v3 POST.
    Body is a JSON array of event objects.
    """
    body = await request.body()

    # Signature verification (optional in dev)
    signature = request.headers.get("X-Twilio-Email-Event-Webhook-Signature", "")
    timestamp = request.headers.get("X-Twilio-Email-Event-Webhook-Timestamp", "")

    if settings.environment == "production" and signature:
        if not verify_sendgrid_signature(body, signature, timestamp):
            raise HTTPException(status_code=403, detail="Invalid webhook signature")

    try:
        events = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if not isinstance(events, list):
        events = [events]

    db = SessionLocal()
    processed = 0
    errors = 0

    try:
        for raw_event in events:
            try:
                # Extract custom_args (SendGrid nests these)
                custom_args = {}
                if "campaign_id" in raw_event:
                    custom_args["campaign_id"] = raw_event["campaign_id"]
                if "contact_id" in raw_event:
                    custom_args["contact_id"] = raw_event["contact_id"]

                event = SendGridEvent(
                    email=raw_event.get("email", ""),
                    timestamp=raw_event.get("timestamp"),
                    event=raw_event.get("event", ""),
                    sg_message_id=raw_event.get("sg_message_id"),
                    campaign_id=custom_args.get("campaign_id"),
                    contact_id=custom_args.get("contact_id"),
                    url=raw_event.get("url"),
                    type=raw_event.get("type"),
                    reason=raw_event.get("reason"),
                    status=raw_event.get("status"),
                )

                handler = EVENT_HANDLERS.get(event.event)
                if not handler:
                    logger.debug(f"Unhandled SendGrid event type: {event.event}")
                    continue

                send_record = _find_send_record(db, event)
                if not send_record:
                    logger.warning(f"No EmailSend found for event: {event.event} / {event.email}")
                    continue

                handler(db, event, send_record)
                processed += 1

            except Exception as e:
                logger.error(f"Error processing SendGrid event: {e}")
                errors += 1

        db.commit()

    except Exception as e:
        db.rollback()
        logger.exception(f"SendGrid webhook batch failed: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")
    finally:
        db.close()

    return {"processed": processed, "errors": errors}

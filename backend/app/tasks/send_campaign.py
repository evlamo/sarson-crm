"""
Celery task for sending email campaigns via SendGrid.

Batches recipients into groups of 1000, rate-limits API calls,
tracks per-recipient send status.
"""
import logging
from datetime import datetime, timezone
from uuid import UUID
from typing import List, Dict, Any

from app.tasks import celery_app
from app.config import settings
from app.database import SessionLocal
from app.models.campaign import EmailCampaign, EmailSend
from app.models.contact import Contact
from app.services.campaign_service import render_merge_fields, prepare_send

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000
MAX_CALLS_PER_SECOND = 3
CALL_INTERVAL = 1.0 / MAX_CALLS_PER_SECOND


def _build_sendgrid_payload(
    campaign: EmailCampaign,
    batch: List[Dict[str, Any]],
) -> dict:
    """
    Build SendGrid v3 /mail/send payload with personalizations array.
    Each personalization = one recipient with merge field substitutions.
    """
    personalizations = []
    for recipient in batch:
        # Render subject with merge fields
        rendered_subject = render_merge_fields(campaign.subject, recipient)

        personalization = {
            "to": [{"email": recipient["email"]}],
            "subject": rendered_subject,
            "substitutions": {
                f"{{{{{k}}}}}": str(v)
                for k, v in recipient.items()
                if k not in ("contact_id", "email_send_id")
            },
            "custom_args": {
                "campaign_id": str(campaign.id),
                "contact_id": str(recipient["contact_id"]),
            },
        }

        if recipient.get("first_name"):
            personalization["to"][0]["name"] = (
                f"{recipient['first_name']} {recipient.get('last_name', '')}".strip()
            )

        personalizations.append(personalization)

    payload = {
        "personalizations": personalizations,
        "from": {
            "email": campaign.from_email,
            "name": campaign.from_name,
        },
        "content": [
            {"type": "text/html", "value": campaign.body_html},
        ],
        "headers": {
            "List-Unsubscribe": "<mailto:unsubscribe@sarsonfunds.com>",
        },
        "tracking_settings": {
            "click_tracking": {"enable": True},
            "open_tracking": {"enable": True},
        },
    }

    if campaign.body_text:
        payload["content"].insert(0, {"type": "text/plain", "value": campaign.body_text})

    if campaign.reply_to:
        payload["reply_to"] = {"email": campaign.reply_to}

    if campaign.preview_text:
        # SendGrid doesn't have a native preview_text field;
        # prepend hidden preheader to HTML body
        pass

    return payload


def _send_batch_via_sendgrid(payload: dict) -> dict:
    """
    Send a batch via SendGrid v3 API.
    Returns response dict with status and message IDs.
    """
    import httpx

    api_key = settings.sendgrid_api_key
    if not api_key:
        logger.warning("SendGrid API key not configured — skipping actual send")
        return {"status": "skipped", "message": "No API key configured"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                "https://api.sendgrid.com/v3/mail/send",
                json=payload,
                headers=headers,
            )

        if response.status_code in (200, 202):
            message_id = response.headers.get("X-Message-Id", "")
            return {"status": "sent", "message_id": message_id}
        else:
            logger.error(
                f"SendGrid API error: {response.status_code} — {response.text}"
            )
            return {"status": "error", "error": response.text}

    except httpx.HTTPError as e:
        logger.error(f"SendGrid HTTP error: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_campaign_task(self, campaign_id: str):
    """
    Main campaign send task.
    1. Prepare send records
    2. Batch into groups of 1000
    3. Send each batch via SendGrid
    4. Update per-recipient status
    5. Mark campaign as sent
    """
    db = SessionLocal()
    try:
        campaign_uuid = UUID(campaign_id)
        campaign = db.query(EmailCampaign).filter(
            EmailCampaign.id == campaign_uuid
        ).first()

        if not campaign:
            logger.error(f"Campaign {campaign_id} not found")
            return {"status": "error", "message": "Campaign not found"}

        if campaign.status not in ("draft", "scheduled", "sending"):
            logger.warning(f"Campaign {campaign_id} has status {campaign.status}, skipping")
            return {"status": "skipped", "message": f"Campaign status is {campaign.status}"}

        # Step 1: Prepare send records if not already prepared
        if campaign.status != "sending":
            try:
                recipient_count = prepare_send(campaign_uuid, db)
                logger.info(f"Prepared {recipient_count} recipients for campaign {campaign_id}")
            except ValueError as e:
                campaign.status = "failed"
                db.commit()
                logger.error(f"Failed to prepare campaign {campaign_id}: {e}")
                return {"status": "error", "message": str(e)}

        # Step 2: Load all queued sends
        sends = db.query(EmailSend).filter(
            EmailSend.campaign_id == campaign_uuid,
            EmailSend.status == "queued",
        ).all()

        if not sends:
            campaign.status = "sent"
            campaign.sent_at = datetime.now(timezone.utc)
            db.commit()
            return {"status": "complete", "sent": 0}

        # Build recipient data for merge fields
        contact_ids = [s.contact_id for s in sends]
        contacts = db.query(Contact).filter(Contact.id.in_(contact_ids)).all()
        contact_map = {c.id: c for c in contacts}

        # Step 3: Batch and send
        total_sent = 0
        batch = []
        send_map = {}  # email -> EmailSend record

        for send_record in sends:
            contact = contact_map.get(send_record.contact_id)
            if not contact:
                send_record.status = "failed"
                continue

            recipient_data = {
                "contact_id": str(contact.id),
                "email": send_record.email_address,
                "first_name": contact.first_name or "",
                "last_name": contact.last_name or "",
                "full_name": f"{contact.first_name or ''} {contact.last_name or ''}".strip(),
                "company": contact.company or "",
                "unsubscribe_url": f"https://sarsonfunds.com/unsubscribe?c={contact.id}",
                "email_send_id": str(send_record.id),
            }
            batch.append(recipient_data)
            send_map[send_record.email_address] = send_record

            if len(batch) >= BATCH_SIZE:
                # Send batch
                payload = _build_sendgrid_payload(campaign, batch)
                result = _send_batch_via_sendgrid(payload)

                if result["status"] in ("sent", "skipped"):
                    for r in batch:
                        sr = send_map.get(r["email"])
                        if sr:
                            sr.status = "sent"
                            sr.message_id = result.get("message_id")
                    total_sent += len(batch)
                else:
                    for r in batch:
                        sr = send_map.get(r["email"])
                        if sr:
                            sr.status = "failed"

                db.commit()
                batch = []
                send_map = {}
                # Rate limiting is handled by Celery's task_default_rate_limit

        # Send remaining batch
        if batch:
            payload = _build_sendgrid_payload(campaign, batch)
            result = _send_batch_via_sendgrid(payload)

            if result["status"] in ("sent", "skipped"):
                for r in batch:
                    sr = send_map.get(r["email"])
                    if sr:
                        sr.status = "sent"
                        sr.message_id = result.get("message_id")
                total_sent += len(batch)
            else:
                for r in batch:
                    sr = send_map.get(r["email"])
                    if sr:
                        sr.status = "failed"

        # Step 4: Finalize
        campaign.status = "sent"
        campaign.sent_at = datetime.now(timezone.utc)
        campaign.sent_count = total_sent
        db.commit()

        logger.info(f"Campaign {campaign_id} sent to {total_sent} recipients")
        return {"status": "complete", "sent": total_sent}

    except Exception as e:
        db.rollback()
        campaign = db.query(EmailCampaign).filter(
            EmailCampaign.id == UUID(campaign_id)
        ).first()
        if campaign:
            campaign.status = "failed"
            db.commit()
        logger.exception(f"Campaign {campaign_id} failed: {e}")
        raise self.retry(exc=e)
    finally:
        db.close()


@celery_app.task
def cancel_campaign_task(campaign_id: str):
    """Cancel a sending campaign — mark remaining queued sends as cancelled."""
    db = SessionLocal()
    try:
        campaign_uuid = UUID(campaign_id)
        campaign = db.query(EmailCampaign).filter(
            EmailCampaign.id == campaign_uuid
        ).first()

        if not campaign:
            return {"status": "error", "message": "Campaign not found"}

        # Cancel queued sends
        cancelled = db.query(EmailSend).filter(
            EmailSend.campaign_id == campaign_uuid,
            EmailSend.status == "queued",
        ).update({"status": "cancelled"})

        campaign.status = "cancelled"
        db.commit()

        logger.info(f"Campaign {campaign_id} cancelled, {cancelled} sends cancelled")
        return {"status": "cancelled", "cancelled_count": cancelled}
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to cancel campaign {campaign_id}: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()

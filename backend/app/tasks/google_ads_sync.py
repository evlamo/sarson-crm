"""
Celery task: sync pending Google Ads conversions in batches.
Runs every 15 minutes via Celery Beat.
"""
import logging
from datetime import datetime, timezone, timedelta
from app.database import SessionLocal
from app.models.contact import Contact
from app.models.google_ads import ConversionSyncHistory, GoogleAdsConversionAction
from app.services import google_ads_service
from app.tasks import celery_app

logger = logging.getLogger(__name__)
BATCH_SIZE = 50
MAX_RETRIES = 3


@celery_app.task(name="sync_google_ads_conversions")
def sync_google_ads_conversions():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        pending_contacts = db.query(Contact).filter(
            Contact.gclid.isnot(None),
            Contact.gclid_expires_at > now,
            Contact.conversion_status.in_(["pending", None]),
            Contact.deleted_at.is_(None),
        ).limit(BATCH_SIZE).all()

        retry_records = db.query(ConversionSyncHistory).filter(
            ConversionSyncHistory.sync_status == "transient_error",
            ConversionSyncHistory.retry_count < MAX_RETRIES,
            ConversionSyncHistory.next_retry_at <= now,
        ).limit(BATCH_SIZE).all()

        synced = 0
        errors = 0

        for contact in pending_contacts:
            action = db.query(GoogleAdsConversionAction).filter(
                GoogleAdsConversionAction.trigger_on_status == contact.status,
                GoogleAdsConversionAction.is_active == True,
            ).first()
            if not action:
                logger.warning(f"Contact {contact.id}: no active conversion action matches status '{contact.status}' — skipping")
                contact.conversion_status = "no_action_configured"
                db.add(contact)
                continue
            if not action.google_conversion_action_id:
                logger.warning(f"Contact {contact.id}: action '{action.name}' has no Google Action ID — skipping")
                contact.conversion_status = "no_action_configured"
                db.add(contact)
                continue

            value = float(contact.conversion_value or action.default_value or 0)
            conversion_time = contact.conversion_synced_at or contact.created_at or now

            result = google_ads_service.upload_click_conversion_sync(
                gclid=contact.gclid,
                conversion_action_id=action.google_conversion_action_id,
                conversion_time=conversion_time,
                conversion_value=value,
                email=contact.email,
            )

            history = ConversionSyncHistory(
                contact_id=contact.id, gclid=contact.gclid, conversion_name=action.name,
                conversion_value=value, conversion_time=conversion_time,
                hashed_email=google_ads_service.hash_email(contact.email) if contact.email else None,
                sync_status=result["status"], error_message=result.get("error"),
                error_code=result.get("error_code"), google_response=result.get("response"),
                synced_at=now if result["status"] == "success" else None,
            )
            db.add(history)

            if result["status"] == "success":
                contact.conversion_status = "synced"
                contact.conversion_synced = True
                contact.conversion_synced_at = now
                synced += 1
            elif result["status"] == "permanent_error":
                contact.conversion_status = "permanent_error"
                errors += 1
            else:
                contact.conversion_status = "transient_error"
                history.retry_count = 1
                history.next_retry_at = now + timedelta(minutes=15 * (2 ** 1))
                errors += 1

        for record in retry_records:
            action = db.query(GoogleAdsConversionAction).filter(
                GoogleAdsConversionAction.name == record.conversion_name,
                GoogleAdsConversionAction.is_active == True,
            ).first()
            action_id = action.google_conversion_action_id if action else ""

            result = google_ads_service.upload_click_conversion_sync(
                gclid=record.gclid,
                conversion_action_id=action_id,
                conversion_time=record.conversion_time,
                conversion_value=float(record.conversion_value or 0),
                email=None,
            )

            record.retry_count += 1
            record.google_response = result.get("response")
            record.error_message = result.get("error")

            if result["status"] == "success":
                record.sync_status = "success"
                record.synced_at = now
                synced += 1
            elif result["status"] == "permanent_error" or record.retry_count >= MAX_RETRIES:
                record.sync_status = "permanent_error"
                errors += 1
            else:
                record.next_retry_at = now + timedelta(minutes=15 * (2 ** record.retry_count))

        db.commit()
        logger.info(f"Google Ads sync: {synced} synced, {errors} errors")
        return {"synced": synced, "errors": errors}

    except Exception as e:
        db.rollback()
        logger.exception(f"Google Ads sync task failed: {e}")
        raise
    finally:
        db.close()

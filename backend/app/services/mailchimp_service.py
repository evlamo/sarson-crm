"""
Mailchimp API integration service.
Uses httpx for async HTTP. Auth: HTTP Basic with anystring:{api_key}.
"""
import hashlib
import logging
from typing import List, Optional

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models.contact import Contact

logger = logging.getLogger(__name__)


def _check_configured():
    if not settings.mailchimp_api_key:
        raise HTTPException(
            status_code=400,
            detail="Mailchimp API key not configured. Add MAILCHIMP_API_KEY to your .env file.",
        )


def _base_url() -> str:
    prefix = settings.mailchimp_server_prefix
    if not prefix and settings.mailchimp_api_key:
        # Extract from API key suffix (e.g. "xxx-us19")
        prefix = settings.mailchimp_api_key.rsplit("-", 1)[-1]
    return f"https://{prefix}.api.mailchimp.com/3.0"


def get_client() -> httpx.AsyncClient:
    _check_configured()
    return httpx.AsyncClient(
        base_url=_base_url(),
        auth=("anystring", settings.mailchimp_api_key),
        timeout=30.0,
    )


def _subscriber_hash(email: str) -> str:
    """MD5 hash of lowercase email — Mailchimp's member identifier."""
    return hashlib.md5(email.lower().strip().encode()).hexdigest()


async def get_or_create_audience(name: str, from_name: str, reply_to: str) -> str:
    """Returns list_id. Uses default audience if configured, else creates one."""
    _check_configured()

    if settings.mailchimp_audience_id:
        # Verify it exists
        async with get_client() as client:
            r = await client.get(f"/lists/{settings.mailchimp_audience_id}")
            if r.status_code == 200:
                return settings.mailchimp_audience_id

    # Create a new audience
    async with get_client() as client:
        payload = {
            "name": name,
            "contact": {
                "company": "Sarson Funds",
                "address1": "",
                "city": "",
                "state": "",
                "zip": "",
                "country": "US",
            },
            "permission_reminder": "You are receiving this email because you opted in via our website or have a business relationship with Sarson Funds.",
            "campaign_defaults": {
                "from_name": from_name,
                "from_email": reply_to,
                "subject": "",
                "language": "en",
            },
            "email_type_option": True,
        }
        r = await client.post("/lists", json=payload)
        if r.status_code not in (200, 201):
            logger.error(f"Mailchimp create audience failed: {r.status_code} {r.text}")
            raise HTTPException(status_code=502, detail=f"Mailchimp API error: {r.text}")
        return r.json()["id"]


async def batch_upsert_members(list_id: str, contacts: List[dict]) -> dict:
    """
    Upsert contacts into a Mailchimp audience in batches of 500.
    Each contact dict: {email, first_name, last_name, ...}
    Returns {added, updated, errors}.
    """
    _check_configured()
    added = 0
    updated = 0
    errors = 0

    async with get_client() as client:
        for i in range(0, len(contacts), 500):
            batch = contacts[i : i + 500]
            members = []
            for c in batch:
                members.append({
                    "email_address": c["email"],
                    "status_if_new": "subscribed",
                    "status": "subscribed",
                    "merge_fields": {
                        "FNAME": c.get("first_name", ""),
                        "LNAME": c.get("last_name", ""),
                    },
                })

            r = await client.post(
                f"/lists/{list_id}",
                json={"members": members, "update_existing": True},
            )
            if r.status_code not in (200, 201):
                logger.error(f"Mailchimp batch upsert failed: {r.status_code} {r.text}")
                errors += len(batch)
                continue

            data = r.json()
            added += data.get("new_members", 0) if isinstance(data.get("new_members"), int) else len(data.get("new_members", []))
            updated += data.get("updated_members", 0) if isinstance(data.get("updated_members"), int) else len(data.get("updated_members", []))
            errors += len(data.get("errors", []))

    return {"added": added, "updated": updated, "errors": errors}


async def create_campaign(list_id: str, subject: str, from_name: str, reply_to: str, title: str) -> str:
    """Create a Mailchimp campaign. Returns mailchimp_campaign_id."""
    _check_configured()

    async with get_client() as client:
        payload = {
            "type": "regular",
            "recipients": {"list_id": list_id},
            "settings": {
                "subject_line": subject,
                "title": title,
                "from_name": from_name,
                "reply_to": reply_to,
            },
        }
        r = await client.post("/campaigns", json=payload)
        if r.status_code not in (200, 201):
            logger.error(f"Mailchimp create campaign failed: {r.status_code} {r.text}")
            raise HTTPException(status_code=502, detail=f"Mailchimp API error: {r.text}")
        return r.json()["id"]


async def set_campaign_content(campaign_id: str, html: str, plain_text: str = None) -> bool:
    _check_configured()
    async with get_client() as client:
        payload = {"html": html}
        if plain_text:
            payload["plain_text"] = plain_text
        r = await client.put(f"/campaigns/{campaign_id}/content", json=payload)
        if r.status_code not in (200, 201, 204):
            logger.error(f"Mailchimp set content failed: {r.status_code} {r.text}")
            raise HTTPException(status_code=502, detail=f"Mailchimp API error: {r.text}")
        return True


async def send_campaign(campaign_id: str) -> bool:
    _check_configured()
    async with get_client() as client:
        r = await client.post(f"/campaigns/{campaign_id}/actions/send")
        if r.status_code not in (200, 204):
            logger.error(f"Mailchimp send failed: {r.status_code} {r.text}")
            raise HTTPException(status_code=502, detail=f"Mailchimp API error: {r.text}")
        return True


async def get_campaign_stats(campaign_id: str) -> dict:
    _check_configured()
    async with get_client() as client:
        r = await client.get(f"/reports/{campaign_id}")
        if r.status_code != 200:
            logger.error(f"Mailchimp stats failed: {r.status_code} {r.text}")
            raise HTTPException(status_code=502, detail=f"Mailchimp API error: {r.text}")
        data = r.json()
        return {
            "opens": data.get("opens", {}).get("unique_opens", 0),
            "clicks": data.get("clicks", {}).get("unique_clicks", 0),
            "bounces": data.get("bounces", {}).get("hard_bounces", 0) + data.get("bounces", {}).get("soft_bounces", 0),
            "unsubscribes": data.get("unsubscribed", 0),
        }


def filter_eligible_contacts(db: Session, contact_ids: List) -> List[dict]:
    """Filter out unsubscribed/bounced contacts. Returns list of dicts."""
    contacts = db.query(Contact).filter(
        Contact.id.in_(contact_ids),
        Contact.email_unsubscribed != True,
        Contact.email_bounced != True,
        Contact.email.isnot(None),
    ).all()
    return [
        {
            "id": str(c.id),
            "email": c.email,
            "first_name": c.first_name or "",
            "last_name": c.last_name or "",
        }
        for c in contacts
    ]

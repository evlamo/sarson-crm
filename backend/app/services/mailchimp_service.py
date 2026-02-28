"""
Mailchimp Marketing API v3 service.
Architecture:
  - ONE main audience (list) per account, configured via MAILCHIMP_AUDIENCE_ID
  - Members upserted with merge fields (FNAME, LNAME, PHONE, COMPANY)
  - Campaigns created against the main audience with optional segment_opts
  - Full send checklist validation before send
  - Webhook handling for unsubscribes/bounces
"""
import hashlib
import logging
from typing import List, Optional, Dict, Any
import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.config import settings
from app.models.contact import Contact

logger = logging.getLogger(__name__)

# ── Client ──────────────────────────────────────────────────────────────────

def _check_configured():
    if not settings.mailchimp_api_key:
        raise HTTPException(
            status_code=503,
            detail="Mailchimp API key not configured. Add MAILCHIMP_API_KEY to your environment.",
        )

def _base_url() -> str:
    prefix = settings.mailchimp_server_prefix
    if not prefix and settings.mailchimp_api_key:
        prefix = settings.mailchimp_api_key.rsplit("-", 1)[-1]
    if not prefix:
        raise HTTPException(status_code=503, detail="Cannot determine Mailchimp server prefix.")
    return f"https://{prefix}.api.mailchimp.com/3.0"

def get_client() -> httpx.AsyncClient:
    _check_configured()
    return httpx.AsyncClient(
        base_url=_base_url(),
        auth=("anystring", settings.mailchimp_api_key),
        timeout=30.0,
    )

def subscriber_hash(email: str) -> str:
    return hashlib.md5(email.lower().strip().encode()).hexdigest()

# ── Audience ─────────────────────────────────────────────────────────────────

async def get_main_audience_id() -> str:
    """
    Returns the configured audience ID, or creates the main audience.
    Always use ONE audience. Campaigns target it with segment_opts.
    """
    _check_configured()
    if settings.mailchimp_audience_id:
        async with get_client() as client:
            r = await client.get(f"/lists/{settings.mailchimp_audience_id}")
            if r.status_code == 200:
                return settings.mailchimp_audience_id
            logger.warning(f"Configured audience {settings.mailchimp_audience_id} not found, will create new.")

    async with get_client() as client:
        payload = {
            "name": "Sarson Funds - Main Audience",
            "contact": {
                "company": "Sarson Funds",
                "address1": "123 Main St",
                "city": "Omaha",
                "state": "NE",
                "zip": "68102",
                "country": "US",
            },
            "permission_reminder": "You are receiving this email because you have a business relationship with Sarson Funds or have opted in to our communications.",
            "campaign_defaults": {
                "from_name": "Sarson Funds",
                "from_email": settings.mailchimp_from_email or "info@sarsonfunds.com",
                "subject": "",
                "language": "en",
            },
            "email_type_option": True,
            "double_optin": False,
        }
        r = await client.post("/lists", json=payload)
        if r.status_code not in (200, 201):
            raise HTTPException(status_code=502, detail=f"Failed to create Mailchimp audience: {r.text}")
        audience_id = r.json()["id"]
        logger.info(f"Created Mailchimp audience: {audience_id}. Set MAILCHIMP_AUDIENCE_ID={audience_id} in your .env")
        return audience_id

async def get_audience_info(list_id: str) -> dict:
    async with get_client() as client:
        r = await client.get(f"/lists/{list_id}")
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Mailchimp error: {r.text}")
        return r.json()

# ── Members ──────────────────────────────────────────────────────────────────

async def upsert_member(list_id: str, contact: dict) -> dict:
    """Upsert a single member into a Mailchimp audience."""
    _check_configured()
    email = contact["email"].lower().strip()
    h = subscriber_hash(email)
    payload = {
        "email_address": email,
        "status_if_new": "subscribed",
        "status": "subscribed",
        "merge_fields": {
            "FNAME": contact.get("first_name", "") or "",
            "LNAME": contact.get("last_name", "") or "",
            "PHONE": contact.get("phone", "") or "",
            "COMPANY": contact.get("company", "") or "",
        },
    }
    async with get_client() as client:
        r = await client.put(f"/lists/{list_id}/members/{h}", json=payload)
        if r.status_code not in (200, 201):
            raise HTTPException(status_code=502, detail=f"Failed to upsert member: {r.text}")
        return r.json()

async def batch_upsert_members(list_id: str, contacts: List[dict]) -> dict:
    """
    Batch upsert contacts into a Mailchimp audience (max 500 per request).
    Uses POST /lists/{list_id} with update_existing=True.
    """
    _check_configured()
    total_added = 0
    total_updated = 0
    total_errors = 0

    async with get_client() as client:
        for i in range(0, len(contacts), 500):
            batch = contacts[i:i + 500]
            members = []
            for c in batch:
                members.append({
                    "email_address": c["email"].lower().strip(),
                    "status_if_new": "subscribed",
                    "status": "subscribed",
                    "merge_fields": {
                        "FNAME": c.get("first_name", "") or "",
                        "LNAME": c.get("last_name", "") or "",
                        "PHONE": c.get("phone", "") or "",
                        "COMPANY": c.get("company", "") or "",
                    },
                })
            r = await client.post(
                f"/lists/{list_id}",
                json={"members": members, "update_existing": True},
            )
            if r.status_code not in (200, 201):
                logger.error(f"Mailchimp batch upsert failed: {r.status_code} {r.text}")
                total_errors += len(batch)
                continue
            data = r.json()
            nm = data.get("new_members", [])
            um = data.get("updated_members", [])
            total_added += len(nm) if isinstance(nm, list) else nm
            total_updated += len(um) if isinstance(um, list) else um
            total_errors += len(data.get("errors", []))

    return {"added": total_added, "updated": total_updated, "errors": total_errors}

async def get_member_status(list_id: str, email: str) -> Optional[str]:
    """Get a member's subscription status. Returns None if not found."""
    h = subscriber_hash(email)
    try:
        async with get_client() as client:
            r = await client.get(f"/lists/{list_id}/members/{h}")
            if r.status_code == 200:
                return r.json().get("status")
            return None
    except Exception:
        return None

async def unsubscribe_member(list_id: str, email: str) -> bool:
    """Mark a member as unsubscribed in Mailchimp."""
    h = subscriber_hash(email)
    async with get_client() as client:
        r = await client.patch(
            f"/lists/{list_id}/members/{h}",
            json={"status": "unsubscribed"}
        )
        return r.status_code in (200, 201)

# ── Campaigns ────────────────────────────────────────────────────────────────

async def create_mc_campaign(
    list_id: str,
    subject: str,
    from_name: str,
    reply_to: str,
    title: str,
    preview_text: str = "",
    to_name: str = "*|FNAME|* *|LNAME|*",
    tracking_opens: bool = True,
    tracking_html_clicks: bool = True,
    google_analytics_tag: str = "",
    segment_opts: Optional[dict] = None,
) -> str:
    """Create a Mailchimp regular campaign. Returns mc_campaign_id."""
    _check_configured()
    recipients: dict = {"list_id": list_id}
    if segment_opts:
        recipients["segment_opts"] = segment_opts

    payload = {
        "type": "regular",
        "recipients": recipients,
        "settings": {
            "subject_line": subject,
            "preview_text": preview_text,
            "title": title,
            "from_name": from_name,
            "reply_to": reply_to,
            "to_name": to_name,
            "auto_footer": True,
            "inline_css": True,
        },
        "tracking": {
            "opens": tracking_opens,
            "html_clicks": tracking_html_clicks,
            "text_clicks": False,
            "google_analytics": google_analytics_tag or "",
        },
    }

    async with get_client() as client:
        r = await client.post("/campaigns", json=payload)
        if r.status_code not in (200, 201):
            logger.error(f"Mailchimp create campaign failed: {r.status_code} {r.text}")
            raise HTTPException(status_code=502, detail=f"Mailchimp API error: {r.text}")
        return r.json()["id"]

async def set_campaign_content(mc_campaign_id: str, html: str, plain_text: str = "") -> bool:
    """
    Set HTML (and optionally plain text) content for a Mailchimp campaign.
    With auto_footer=True (set in create_mc_campaign), Mailchimp auto-appends
    the required unsubscribe footer.
    """
    _check_configured()
    payload: dict = {"html": html}
    if plain_text:
        payload["plain_text"] = plain_text

    async with get_client() as client:
        r = await client.put(f"/campaigns/{mc_campaign_id}/content", json=payload)
        if r.status_code not in (200, 201, 204):
            logger.error(f"Mailchimp set content failed: {r.status_code} {r.text}")
            raise HTTPException(status_code=502, detail=f"Mailchimp content error: {r.text}")
        return True

async def get_send_checklist(mc_campaign_id: str) -> dict:
    """
    Get the send checklist for a Mailchimp campaign.
    Returns {is_ready: bool, items: [{type, id, heading, details}]}
    """
    _check_configured()
    async with get_client() as client:
        r = await client.get(f"/campaigns/{mc_campaign_id}/send-checklist")
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Mailchimp checklist error: {r.text}")
        return r.json()

async def send_test_email(mc_campaign_id: str, test_emails: List[str], send_type: str = "html") -> bool:
    """Send a test version of the campaign to specified addresses."""
    _check_configured()
    async with get_client() as client:
        r = await client.post(
            f"/campaigns/{mc_campaign_id}/actions/test",
            json={"test_emails": test_emails, "send_type": send_type},
        )
        if r.status_code not in (200, 204):
            raise HTTPException(status_code=502, detail=f"Mailchimp test send error: {r.text}")
        return True

async def send_mc_campaign(mc_campaign_id: str) -> bool:
    """Send the campaign immediately."""
    _check_configured()
    async with get_client() as client:
        r = await client.post(f"/campaigns/{mc_campaign_id}/actions/send")
        if r.status_code not in (200, 204):
            raise HTTPException(status_code=502, detail=f"Mailchimp send error: {r.text}")
        return True

async def schedule_mc_campaign(mc_campaign_id: str, schedule_time: str) -> bool:
    """Schedule a campaign to send at a specific time (ISO 8601 UTC)."""
    _check_configured()
    async with get_client() as client:
        r = await client.post(
            f"/campaigns/{mc_campaign_id}/actions/schedule",
            json={"schedule_time": schedule_time},
        )
        if r.status_code not in (200, 204):
            raise HTTPException(status_code=502, detail=f"Mailchimp schedule error: {r.text}")
        return True

async def unschedule_mc_campaign(mc_campaign_id: str) -> bool:
    """Unschedule a scheduled campaign (reverts to draft)."""
    _check_configured()
    async with get_client() as client:
        r = await client.post(f"/campaigns/{mc_campaign_id}/actions/unschedule")
        return r.status_code in (200, 204)

async def cancel_mc_send(mc_campaign_id: str) -> bool:
    """Cancel a campaign that is currently sending."""
    _check_configured()
    async with get_client() as client:
        r = await client.post(f"/campaigns/{mc_campaign_id}/actions/cancel-send")
        return r.status_code in (200, 204)

async def get_mc_campaign_info(mc_campaign_id: str) -> dict:
    """Get full campaign info from Mailchimp."""
    async with get_client() as client:
        r = await client.get(f"/campaigns/{mc_campaign_id}")
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Mailchimp error: {r.text}")
        return r.json()

async def get_mc_campaign_stats(mc_campaign_id: str) -> dict:
    """Get detailed stats from Mailchimp reports."""
    _check_configured()
    async with get_client() as client:
        r = await client.get(f"/reports/{mc_campaign_id}")
        if r.status_code != 200:
            if r.status_code == 404:
                return {"error": "Report not yet available. Campaign may not have been sent yet."}
            raise HTTPException(status_code=502, detail=f"Mailchimp stats error: {r.text}")
        data = r.json()
        opens = data.get("opens", {})
        clicks = data.get("clicks", {})
        bounces = data.get("bounces", {})
        return {
            "emails_sent": data.get("emails_sent", 0),
            "unique_opens": opens.get("unique_opens", 0),
            "open_rate": opens.get("open_rate", 0),
            "total_opens": opens.get("opens_total", 0),
            "unique_clicks": clicks.get("unique_clicks", 0),
            "click_rate": clicks.get("click_rate", 0),
            "total_clicks": clicks.get("clicks_total", 0),
            "hard_bounces": bounces.get("hard_bounces", 0),
            "soft_bounces": bounces.get("soft_bounces", 0),
            "unsubscribes": data.get("unsubscribed", 0),
            "complaints": data.get("abuse_reports", 0),
            "last_send_time": data.get("send_time"),
        }

async def get_mc_lists() -> List[dict]:
    """List all audiences in the Mailchimp account."""
    _check_configured()
    async with get_client() as client:
        r = await client.get("/lists", params={"count": 100})
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Mailchimp error: {r.text}")
        return r.json().get("lists", [])

# ── Helpers ──────────────────────────────────────────────────────────────────

def filter_eligible_contacts(db: Session, contact_ids: List) -> List[dict]:
    """Filter out contacts without email, unsubscribed, or bounced. Returns list of dicts."""
    contacts = db.query(Contact).filter(
        Contact.id.in_(contact_ids),
        Contact.deleted_at.is_(None),
        Contact.email.isnot(None),
        Contact.email != "",
        Contact.email_unsubscribed.isnot(True),
        Contact.email_bounced.isnot(True),
    ).all()
    return [
        {
            "id": str(c.id),
            "email": c.email,
            "first_name": c.first_name or "",
            "last_name": c.last_name or "",
            "phone": c.phone or "",
            "company": c.company or "",
            "title": c.title or "",
        }
        for c in contacts
    ]

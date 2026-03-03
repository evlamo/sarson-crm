"""Campaign Stats router — Mailchimp live data or demo fallback."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import List, Optional

import redis
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.config import settings as app_settings
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/campaign-stats", tags=["campaign-stats"])

# ── Schemas ────────────────────────────────────────────────────────────────

class CampaignStat(BaseModel):
    id: str
    name: str
    send_date: Optional[str] = None
    recipients: int = 0
    delivered: int = 0
    opens: int = 0
    clicks: int = 0
    unsubscribes: int = 0
    bounces: int = 0
    open_rate: float = 0.0
    click_rate: float = 0.0
    unsubscribe_rate: float = 0.0
    bounce_rate: float = 0.0
    status: str = "sent"


class CampaignSummary(BaseModel):
    total_sent: int = 0
    delivered_rate: float = 0.0
    open_rate: float = 0.0
    click_rate: float = 0.0
    unsubscribe_rate: float = 0.0
    bounce_rate: float = 0.0
    source: str = "demo"


class CampaignStatsResponse(BaseModel):
    campaigns: List[CampaignStat]
    source: str = "demo"


# ── Demo Data ──────────────────────────────────────────────────────────────

DEMO_CAMPAIGNS: List[CampaignStat] = [
    CampaignStat(id="d1", name="Q1 2026 Investor Update", send_date="2026-01-15", recipients=8420, delivered=8310, opens=2744, clicks=498, unsubscribes=12, bounces=110, open_rate=33.0, click_rate=5.99, unsubscribe_rate=0.14, bounce_rate=1.31, status="sent"),
    CampaignStat(id="d2", name="March Newsletter", send_date="2026-03-01", recipients=8650, delivered=8540, opens=2562, clicks=410, unsubscribes=8, bounces=110, open_rate=30.0, click_rate=4.80, unsubscribe_rate=0.09, bounce_rate=1.27, status="sent"),
    CampaignStat(id="d3", name="New Fund Launch: SarsToken ETF", send_date="2026-02-10", recipients=9200, delivered=9085, opens=3180, clicks=736, unsubscribes=18, bounces=115, open_rate=35.0, click_rate=8.10, unsubscribe_rate=0.20, bounce_rate=1.25, status="sent"),
    CampaignStat(id="d4", name="Year-End Performance Report", send_date="2025-12-20", recipients=8100, delivered=7990, opens=2237, clicks=320, unsubscribes=5, bounces=110, open_rate=28.0, click_rate=4.01, unsubscribe_rate=0.06, bounce_rate=1.36, status="sent"),
    CampaignStat(id="d5", name="February Market Insights", send_date="2026-02-01", recipients=8500, delivered=8400, opens=2268, clicks=336, unsubscribes=10, bounces=100, open_rate=27.0, click_rate=4.00, unsubscribe_rate=0.12, bounce_rate=1.18, status="sent"),
    CampaignStat(id="d6", name="Crypto Market Outlook 2026", send_date="2026-01-28", recipients=9500, delivered=9380, opens=3283, clicks=656, unsubscribes=22, bounces=120, open_rate=35.0, click_rate=6.99, unsubscribe_rate=0.23, bounce_rate=1.26, status="sent"),
    CampaignStat(id="d7", name="Q4 2025 Fund Fact Sheets", send_date="2025-11-15", recipients=7800, delivered=7700, opens=1848, clicks=277, unsubscribes=4, bounces=100, open_rate=24.0, click_rate=3.60, unsubscribe_rate=0.05, bounce_rate=1.28, status="sent"),
    CampaignStat(id="d8", name="Webinar Invite: DeFi for Advisors", send_date="2026-02-20", recipients=6200, delivered=6130, opens=1962, clicks=429, unsubscribes=6, bounces=70, open_rate=32.0, click_rate=7.00, unsubscribe_rate=0.10, bounce_rate=1.13, status="sent"),
    CampaignStat(id="d9", name="April Newsletter Draft", send_date=None, recipients=0, delivered=0, opens=0, clicks=0, unsubscribes=0, bounces=0, open_rate=0.0, click_rate=0.0, unsubscribe_rate=0.0, bounce_rate=0.0, status="draft"),
]


def _compute_summary(campaigns: List[CampaignStat], source: str) -> CampaignSummary:
    sent = [c for c in campaigns if c.status == "sent"]
    if not sent:
        return CampaignSummary(source=source)
    total_recipients = sum(c.recipients for c in sent)
    total_delivered = sum(c.delivered for c in sent)
    total_opens = sum(c.opens for c in sent)
    total_clicks = sum(c.clicks for c in sent)
    total_unsubs = sum(c.unsubscribes for c in sent)
    total_bounces = sum(c.bounces for c in sent)
    return CampaignSummary(
        total_sent=total_recipients,
        delivered_rate=round(total_delivered / total_recipients * 100, 1) if total_recipients else 0,
        open_rate=round(total_opens / total_delivered * 100, 1) if total_delivered else 0,
        click_rate=round(total_clicks / total_delivered * 100, 1) if total_delivered else 0,
        unsubscribe_rate=round(total_unsubs / total_delivered * 100, 2) if total_delivered else 0,
        bounce_rate=round(total_bounces / total_recipients * 100, 2) if total_recipients else 0,
        source=source,
    )


def _mailchimp_configured() -> bool:
    return bool(os.getenv("MAILCHIMP_API_KEY") and os.getenv("MAILCHIMP_SERVER_PREFIX"))


async def _fetch_mailchimp() -> List[CampaignStat]:
    import httpx

    api_key = os.environ["MAILCHIMP_API_KEY"]
    server = os.environ["MAILCHIMP_SERVER_PREFIX"]
    if not re.match(r"^us\d+$", server):
        raise HTTPException(status_code=500, detail="Invalid Mailchimp server prefix configuration")
    url = f"https://{server}.api.mailchimp.com/3.0/campaigns"
    params = {
        "count": 50,
        "sort_field": "send_time",
        "sort_dir": "DESC",
        "fields": "campaigns.id,campaigns.settings.title,campaigns.send_time,campaigns.status,campaigns.emails_sent,campaigns.report_summary",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params, auth=("anystring", api_key))
        resp.raise_for_status()
        data = resp.json()

    results: List[CampaignStat] = []
    for c in data.get("campaigns", []):
        settings = c.get("settings", {})
        report = c.get("report_summary", {})
        recipients = c.get("emails_sent", 0) or 0
        opens = report.get("opens", 0)
        clicks = report.get("subscriber_clicks", 0)
        unsubs = report.get("unsubscribes", 0)
        bounces = report.get("hard_bounces", 0) + report.get("soft_bounces", 0)
        delivered = recipients - bounces
        results.append(CampaignStat(
            id=c["id"],
            name=settings.get("title", "Untitled"),
            send_date=c.get("send_time", "")[:10] if c.get("send_time") else None,
            recipients=recipients,
            delivered=delivered,
            opens=opens,
            clicks=clicks,
            unsubscribes=unsubs,
            bounces=bounces,
            open_rate=round(opens / delivered * 100, 1) if delivered else 0,
            click_rate=round(clicks / delivered * 100, 1) if delivered else 0,
            unsubscribe_rate=round(unsubs / delivered * 100, 2) if delivered else 0,
            bounce_rate=round(bounces / recipients * 100, 2) if recipients else 0,
            status=c.get("status", "sent"),
        ))
    return results


# ── Redis Cache ────────────────────────────────────────────────────────────

CACHE_TTL = 300  # 5 minutes

def _get_redis():
    try:
        return redis.from_url(app_settings.redis_url, decode_responses=True)
    except Exception:
        return None


async def _fetch_mailchimp_cached(cache_key: str) -> Optional[List[CampaignStat]]:
    """Fetch from Redis cache or Mailchimp API, caching the result."""
    r = _get_redis()
    if r:
        try:
            cached = r.get(cache_key)
            if cached:
                data = json.loads(cached)
                return [CampaignStat(**c) for c in data]
        except Exception as exc:
            logger.warning("Redis cache read failed: %s", exc)

    campaigns = await _fetch_mailchimp()

    if r:
        try:
            r.setex(cache_key, CACHE_TTL, json.dumps([c.model_dump() for c in campaigns]))
        except Exception as exc:
            logger.warning("Redis cache write failed: %s", exc)

    return campaigns


# ── Routes ─────────────────────────────────────────────────────────────────

@router.get("", response_model=CampaignStatsResponse)
async def get_campaign_stats(current_user: User = Depends(get_current_user)):
    if _mailchimp_configured():
        try:
            campaigns = await _fetch_mailchimp_cached("campaign_stats:list")
            return CampaignStatsResponse(campaigns=campaigns, source="mailchimp")
        except Exception as exc:
            logger.error("Failed to fetch campaign stats from Mailchimp: %s", exc)
    return CampaignStatsResponse(campaigns=DEMO_CAMPAIGNS, source="demo")


@router.get("/summary", response_model=CampaignSummary)
async def get_campaign_summary(current_user: User = Depends(get_current_user)):
    if _mailchimp_configured():
        try:
            campaigns = await _fetch_mailchimp_cached("campaign_stats:list")
            return _compute_summary(campaigns, "mailchimp")
        except Exception as exc:
            logger.error("Failed to fetch campaign summary from Mailchimp: %s", exc)
    return _compute_summary(DEMO_CAMPAIGNS, "demo")


# ── Campaign Detail with Unsubscribers ─────────────────────────────────────────

class UnsubscriberRecord(BaseModel):
    email: str
    contact_id: Optional[str] = None
    contact_name: Optional[str] = None
    reason: Optional[str] = None


class CampaignDetailResponse(BaseModel):
    campaign_id: str
    name: str
    subject: Optional[str] = None
    status: str
    send_date: Optional[str] = None
    sales_campaign_id: Optional[str] = None
    sales_campaign_name: Optional[str] = None
    sent: int = 0
    delivered: int = 0
    opens: int = 0
    unique_opens: int = 0
    clicks: int = 0
    unique_clicks: int = 0
    unsubscribes: int = 0
    bounces: int = 0
    open_rate: float = 0.0
    click_rate: float = 0.0
    unsubscribe_rate: float = 0.0
    bounce_rate: float = 0.0
    unsubscribers: List[UnsubscriberRecord] = []
    mailchimp_required: bool = False


async def _fetch_mc_unsubscribers(mc_campaign_id: str) -> List[dict]:
    """Fetch unsubscriber list from Mailchimp reports API."""
    import httpx
    
    api_key = os.environ.get("MAILCHIMP_API_KEY")
    server = os.environ.get("MAILCHIMP_SERVER_PREFIX")
    if not api_key or not server:
        return []
    
    url = f"https://{server}.api.mailchimp.com/3.0/reports/{mc_campaign_id}/unsubscribed"
    params = {"count": 100}
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params, auth=("anystring", api_key))
            if resp.status_code != 200:
                logger.warning(f"Failed to fetch unsubscribers: {resp.status_code}")
                return []
            data = resp.json()
            return data.get("unsubscribes", [])
    except Exception as exc:
        logger.error(f"Error fetching unsubscribers: {exc}")
        return []


async def _fetch_mc_campaign_report(mc_campaign_id: str) -> Optional[dict]:
    """Fetch campaign report from Mailchimp."""
    import httpx
    
    api_key = os.environ.get("MAILCHIMP_API_KEY")
    server = os.environ.get("MAILCHIMP_SERVER_PREFIX")
    if not api_key or not server:
        return None
    
    url = f"https://{server}.api.mailchimp.com/3.0/reports/{mc_campaign_id}"
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, auth=("anystring", api_key))
            if resp.status_code != 200:
                logger.warning(f"Failed to fetch campaign report: {resp.status_code}")
                return None
            return resp.json()
    except Exception as exc:
        logger.error(f"Error fetching campaign report: {exc}")
        return None


@router.get("/{campaign_id}/detail", response_model=CampaignDetailResponse)
async def get_campaign_detail(
    campaign_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed campaign stats including unsubscriber list.
    campaign_id can be either mailchimp_campaign_id or email_campaigns.id (UUID).
    """
    from app.database import get_db
    from app.models.campaign import EmailCampaign
    from app.models.sales_campaign import SalesCampaign
    from app.models.contact import Contact
    from sqlalchemy.orm import Session
    import uuid as uuid_module
    
    db: Session = next(get_db())
    
    try:
        # Try to find campaign by mailchimp_campaign_id first, then by UUID id
        campaign = db.query(EmailCampaign).filter(
            EmailCampaign.mailchimp_campaign_id == campaign_id
        ).first()
        
        if not campaign:
            # Try parsing as UUID
            try:
                campaign_uuid = uuid_module.UUID(campaign_id)
                campaign = db.query(EmailCampaign).filter(
                    EmailCampaign.id == campaign_uuid
                ).first()
            except (ValueError, AttributeError):
                pass
        
        # Also check demo data
        demo_campaign = next((c for c in DEMO_CAMPAIGNS if c.id == campaign_id), None)
        
        if not campaign and not demo_campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Get sales campaign name if linked
        sales_campaign_name = None
        sales_campaign_id_str = None
        if campaign and campaign.sales_campaign_id:
            sales_campaign = db.query(SalesCampaign).filter(
                SalesCampaign.id == campaign.sales_campaign_id
            ).first()
            if sales_campaign:
                sales_campaign_name = sales_campaign.name
                sales_campaign_id_str = str(campaign.sales_campaign_id)
        
        # Initialize response
        unsubscribers: List[UnsubscriberRecord] = []
        mailchimp_required = False
        
        mc_campaign_id = campaign.mailchimp_campaign_id if campaign else None
        
        # If Mailchimp configured and campaign has mailchimp_campaign_id, fetch from Mailchimp
        if _mailchimp_configured() and mc_campaign_id:
            # Fetch report stats from Mailchimp
            report = await _fetch_mc_campaign_report(mc_campaign_id)
            
            if report:
                opens_data = report.get("opens", {})
                clicks_data = report.get("clicks", {})
                bounces_data = report.get("bounces", {})
                
                sent = report.get("emails_sent", 0)
                hard_bounces = bounces_data.get("hard_bounces", 0)
                soft_bounces = bounces_data.get("soft_bounces", 0)
                bounces = hard_bounces + soft_bounces
                delivered = sent - bounces
                unique_opens = opens_data.get("unique_opens", 0)
                total_opens = opens_data.get("opens_total", 0)
                unique_clicks = clicks_data.get("unique_clicks", 0)
                total_clicks = clicks_data.get("clicks_total", 0)
                unsubs = report.get("unsubscribed", 0)
                
                open_rate = round(opens_data.get("open_rate", 0) * 100, 1)
                click_rate = round(clicks_data.get("click_rate", 0) * 100, 1)
                unsub_rate = round(unsubs / delivered * 100, 2) if delivered else 0
                bounce_rate = round(bounces / sent * 100, 2) if sent else 0
                
                # Fetch unsubscribers list
                mc_unsubs = await _fetch_mc_unsubscribers(mc_campaign_id)
                
                # Match against CRM contacts
                for u in mc_unsubs:
                    email = u.get("email_address", "")
                    reason = u.get("reason", "")
                    
                    # Try to find contact by email
                    contact = db.query(Contact).filter(
                        Contact.email == email
                    ).first() if email else None
                    
                    contact_name = None
                    contact_id = None
                    if contact:
                        contact_id = str(contact.id)
                        first = contact.first_name or ""
                        last = contact.last_name or ""
                        contact_name = f"{first} {last}".strip() or None
                    
                    unsubscribers.append(UnsubscriberRecord(
                        email=email,
                        contact_id=contact_id,
                        contact_name=contact_name,
                        reason=reason,
                    ))
                
                return CampaignDetailResponse(
                    campaign_id=campaign_id,
                    name=campaign.name if campaign else "Unknown",
                    subject=campaign.subject if campaign else None,
                    status=campaign.status if campaign else "sent",
                    send_date=campaign.sent_at.strftime("%Y-%m-%d") if campaign and campaign.sent_at else report.get("send_time", "")[:10] if report.get("send_time") else None,
                    sales_campaign_id=sales_campaign_id_str,
                    sales_campaign_name=sales_campaign_name,
                    sent=sent,
                    delivered=delivered,
                    opens=total_opens,
                    unique_opens=unique_opens,
                    clicks=total_clicks,
                    unique_clicks=unique_clicks,
                    unsubscribes=unsubs,
                    bounces=bounces,
                    open_rate=open_rate,
                    click_rate=click_rate,
                    unsubscribe_rate=unsub_rate,
                    bounce_rate=bounce_rate,
                    unsubscribers=unsubscribers,
                    mailchimp_required=False,
                )
        
        # If demo data
        if demo_campaign and not campaign:
            return CampaignDetailResponse(
                campaign_id=demo_campaign.id,
                name=demo_campaign.name,
                subject=None,
                status=demo_campaign.status,
                send_date=demo_campaign.send_date,
                sales_campaign_id=None,
                sales_campaign_name=None,
                sent=demo_campaign.recipients,
                delivered=demo_campaign.delivered,
                opens=demo_campaign.opens,
                unique_opens=demo_campaign.opens,
                clicks=demo_campaign.clicks,
                unique_clicks=demo_campaign.clicks,
                unsubscribes=demo_campaign.unsubscribes,
                bounces=demo_campaign.bounces,
                open_rate=demo_campaign.open_rate,
                click_rate=demo_campaign.click_rate,
                unsubscribe_rate=demo_campaign.unsubscribe_rate,
                bounce_rate=demo_campaign.bounce_rate,
                unsubscribers=[],
                mailchimp_required=True,
            )
        
        # Fallback to CRM stored stats
        if campaign:
            sent = campaign.sent_count or 0
            bounces = campaign.bounce_count or 0
            delivered = sent - bounces
            unique_opens = campaign.unique_opens or 0
            unique_clicks = campaign.unique_clicks or 0
            unsubs = campaign.unsubscribe_count or 0
            
            open_rate = round(unique_opens / delivered * 100, 1) if delivered else 0
            click_rate = round(unique_clicks / delivered * 100, 1) if delivered else 0
            unsub_rate = round(unsubs / delivered * 100, 2) if delivered else 0
            bounce_rate = round(bounces / sent * 100, 2) if sent else 0
            
            # Without Mailchimp, we cannot get individual unsubscribers
            mailchimp_required = not _mailchimp_configured()
            
            return CampaignDetailResponse(
                campaign_id=str(campaign.id),
                name=campaign.name,
                subject=campaign.subject,
                status=campaign.status,
                send_date=campaign.sent_at.strftime("%Y-%m-%d") if campaign.sent_at else None,
                sales_campaign_id=sales_campaign_id_str,
                sales_campaign_name=sales_campaign_name,
                sent=sent,
                delivered=delivered,
                opens=campaign.open_count or 0,
                unique_opens=unique_opens,
                clicks=campaign.click_count or 0,
                unique_clicks=unique_clicks,
                unsubscribes=unsubs,
                bounces=bounces,
                open_rate=open_rate,
                click_rate=click_rate,
                unsubscribe_rate=unsub_rate,
                bounce_rate=bounce_rate,
                unsubscribers=[],
                mailchimp_required=mailchimp_required,
            )
        
        raise HTTPException(status_code=404, detail="Campaign not found")
    finally:
        db.close()

"""
Campaigns API — CRUD, send, schedule, cancel, stats, recipients.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, desc, union, intersect, case, literal_column, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user, get_admin_user
from app.models.user import User
from app.models.campaign import EmailCampaign, EmailSend
from app.models.segment import Segment
from app.schemas.campaign import (
    CampaignCreate,
    CampaignUpdate,
    CampaignOut,
    CampaignStats,
    CampaignSchedule,
    CampaignListOut,
    EmailSendOut,
    RecipientListOut,
    TestSendRequest,
    MailchimpScheduleRequest,
    MailchimpSyncRequest,
)
from app.services.campaign_service import get_campaign_stats
from app.tasks.send_campaign import send_campaign_task, cancel_campaign_task

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])

# Rate limiter — uses app.state.limiter set in main.py
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)


# ── List Campaigns ─────────────────────────────────────────────────────────

@router.get("", response_model=CampaignListOut)
def list_campaigns(
    status: Optional[str] = None,
    sales_campaign_id: Optional[UUID] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(EmailCampaign)
    if status:
        query = query.filter(EmailCampaign.status == status)
    if sales_campaign_id:
        query = query.filter(EmailCampaign.sales_campaign_id == sales_campaign_id)

    total = query.count()
    items = (
        query.order_by(desc(EmailCampaign.created_at))
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return CampaignListOut(data=items, total=total, page=page, per_page=limit)


# ── Create Campaign ────────────────────────────────────────────────────────

@router.post("", response_model=CampaignOut, status_code=201)
def create_campaign(
    data: CampaignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    # Validate segment exists if provided
    if data.segment_id:
        segment = db.query(Segment).filter(Segment.id == data.segment_id).first()
        if not segment:
            raise HTTPException(status_code=404, detail="Segment not found")

    campaign = EmailCampaign(
        name=data.name,
        subject=data.subject,
        preview_text=data.preview_text,
        body_html=data.body_html,
        body_text=data.body_text,
        template_id=data.template_id,
        segment_id=data.segment_id,
        from_name=data.from_name,
        from_email=data.from_email,
        reply_to=data.reply_to,
        status="draft",
        created_by=current_user.id,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


# ── Get Campaign ───────────────────────────────────────────────────────────

@router.get("/{campaign_id}", response_model=CampaignOut)
def get_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


# ── Update Campaign ────────────────────────────────────────────────────────

@router.patch("/{campaign_id}", response_model=CampaignOut)
def update_campaign(
    campaign_id: UUID,
    data: CampaignUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.status != "draft":
        raise HTTPException(status_code=400, detail="Can only edit draft campaigns")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(campaign, key, value)

    campaign.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(campaign)
    return campaign


# ── Delete Campaign ────────────────────────────────────────────────────────

@router.delete("/{campaign_id}", status_code=204)
def delete_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.status != "draft":
        raise HTTPException(status_code=400, detail="Can only delete draft campaigns")

    db.delete(campaign)
    db.commit()


# ── Send Campaign ──────────────────────────────────────────────────────────

class SendCampaignRequest(BaseModel):
    """Request body for sending a campaign with optional idempotency key."""
    idempotency_key: Optional[str] = None

@router.post("/{campaign_id}/send")
def send_campaign(
    campaign_id: UUID,
    body: Optional[SendCampaignRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.status not in ("draft", "scheduled"):
        raise HTTPException(
            status_code=400,
            detail=f"Campaign status is '{campaign.status}', must be draft or scheduled to send",
        )
    if not campaign.segment_id:
        raise HTTPException(status_code=400, detail="Campaign must have a segment assigned")

    # Handle idempotency key for preventing duplicate sends
    idempotency_key = body.idempotency_key if body else None
    if idempotency_key:
        # Check if this campaign was already sent with this idempotency key
        existing = db.query(EmailCampaign).filter(
            EmailCampaign.idempotency_key == idempotency_key,
            EmailCampaign.id != campaign_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Campaign with idempotency_key '{idempotency_key}' was already sent"
            )
        campaign.idempotency_key = idempotency_key

    campaign.status = "sending"
    db.commit()

    # Queue the Celery task
    task = send_campaign_task.delay(str(campaign.id))

    return {
        "message": "Campaign queued for sending",
        "campaign_id": str(campaign.id),
        "task_id": task.id,
        "idempotency_key": idempotency_key,
    }


# ── Schedule Campaign ─────────────────────────────────────────────────────

@router.post("/{campaign_id}/schedule")
def schedule_campaign(
    campaign_id: UUID,
    data: CampaignSchedule,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.status != "draft":
        raise HTTPException(status_code=400, detail="Can only schedule draft campaigns")
    if data.scheduled_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Scheduled time must be in the future")

    campaign.scheduled_at = data.scheduled_at
    campaign.status = "scheduled"
    db.commit()

    # Schedule Celery task with ETA
    send_campaign_task.apply_async(
        args=[str(campaign.id)],
        eta=data.scheduled_at,
    )

    return {
        "message": "Campaign scheduled",
        "campaign_id": str(campaign.id),
        "scheduled_at": data.scheduled_at.isoformat(),
    }


# ── Cancel Campaign ───────────────────────────────────────────────────────

@router.post("/{campaign_id}/cancel")
def cancel_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.status not in ("scheduled", "sending"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel campaign with status '{campaign.status}'",
        )

    cancel_campaign_task.delay(str(campaign.id))
    return {"message": "Campaign cancellation requested", "campaign_id": str(campaign.id)}


# ── Campaign Stats ─────────────────────────────────────────────────────────

@router.get("/{campaign_id}/stats", response_model=CampaignStats)
def campaign_stats(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return get_campaign_stats(campaign)


# ── Campaign Recipients ───────────────────────────────────────────────────

@router.get("/{campaign_id}/recipients", response_model=RecipientListOut)
def campaign_recipients(
    campaign_id: UUID,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    query = db.query(EmailSend).filter(EmailSend.campaign_id == campaign_id)
    if status:
        query = query.filter(EmailSend.status == status)

    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()

    return RecipientListOut(data=items, total=total, page=page, per_page=limit)


# ── Duplicate Campaign ────────────────────────────────────────────────────

@router.post("/{campaign_id}/duplicate", response_model=CampaignOut, status_code=201)
def duplicate_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    original = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not original:
        raise HTTPException(status_code=404, detail="Campaign not found")

    clone = EmailCampaign(
        name=f"{original.name} (Copy)",
        subject=original.subject,
        preview_text=original.preview_text,
        body_html=original.body_html,
        body_text=original.body_text,
        template_id=original.template_id,
        segment_id=original.segment_id,
        from_name=original.from_name,
        from_email=original.from_email,
        reply_to=original.reply_to,
        status="draft",
        created_by=current_user.id,
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return clone


# ── Mailchimp Integration ─────────────────────────────────────────────────

from app.services import mailchimp_service
from app.models.contact import Contact
from app.models.segment import Segment as SegmentModel


@router.get("/mailchimp/audiences")
async def list_mailchimp_audiences(
    current_user: User = Depends(get_current_user),
):
    """List all Mailchimp audiences in the account."""
    return await mailchimp_service.get_mc_lists()


@router.get("/mailchimp/templates")
async def list_mailchimp_templates(
    current_user: User = Depends(get_current_user),
):
    """List saved Mailchimp templates."""
    return await mailchimp_service.get_mc_templates()


@router.get("/mailchimp/templates/{template_id}/content")
async def get_mailchimp_template_content(
    template_id: int,
    current_user: User = Depends(get_current_user),
):
    """Get the HTML content of a Mailchimp template."""
    html = await mailchimp_service.get_mc_template_content(template_id)
    return {"html": html}


@router.post("/{campaign_id}/sync-mailchimp")
@limiter.limit("10/minute")
async def sync_to_mailchimp(
    request: Request,
    campaign_id: UUID,
    data: MailchimpSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Collect contact IDs from various sources
    contact_ids = set()

    if data.contact_ids:
        contact_ids.update(data.contact_ids)

    if data.segment_id:
        from app.services.segment_service import resolve_campaign_targets
        seg_ids = resolve_campaign_targets("segment", data.segment_id, db)
        contact_ids.update(str(cid) for cid in seg_ids)

    if data.tag_ids:
        from app.models.tag import ContactTag
        from sqlalchemy import select
        stmt = select(ContactTag.c.contact_id).where(
            ContactTag.c.tag_id.in_(data.tag_ids)
        )
        rows = db.execute(stmt).fetchall()
        contact_ids.update(str(r[0]) for r in rows)

    # Campaign Lists (static segments) — the new Lists system
    if data.campaign_list_ids:
        from app.services.campaign_list_service import resolve_combined_segment_contacts
        list_contacts = resolve_combined_segment_contacts(
            data.campaign_list_ids, db
        )
        contact_ids.update(str(c.id) for c in list_contacts)

    if not contact_ids:
        raise HTTPException(status_code=400, detail="No contacts specified. Provide contact_ids, segment_id, tag_ids, or campaign_list_ids.")

    # Filter out unsubscribed/bounced
    eligible = mailchimp_service.filter_eligible_contacts(db, list(contact_ids))
    if not eligible:
        raise HTTPException(status_code=400, detail="No eligible contacts after filtering unsubscribed/bounced.")

    # Step 1: Get the ONE main audience
    audience_id = await mailchimp_service.get_main_audience_id()

    # Step 2: Batch upsert members
    result = await mailchimp_service.batch_upsert_members(audience_id, eligible)

    # Step 3: Create a static segment for targeting (or fall back to tag-based)
    synced_emails = [c["email"] for c in eligible]
    mc_segment_id = None

    if data.campaign_list_ids:
        # Use static segment approach (new Lists system)
        mc_segment_id = await mailchimp_service.create_or_update_static_segment(
            list_id=audience_id,
            segment_name=f"Campaign: {campaign.name[:80]}",
            emails=synced_emails,
            existing_mc_segment_id=None,
        )
    else:
        # Legacy: tag-based approach
        tag_name = f"crm-{str(campaign.id)[:8]}"
        campaign.mailchimp_segment_tag = tag_name
        db.add(campaign)
        db.flush()
        await mailchimp_service.apply_member_tag(audience_id, tag_name, synced_emails)

    # Step 4: Create Mailchimp campaign with segment targeting
    from_name = campaign.from_name or "Sarson Funds"
    reply_to = campaign.reply_to or campaign.from_email

    # Build segment_opts or use segment_id
    segment_opts = None
    if mc_segment_id:
        # No segment_opts needed — we pass saved_segment_id in recipients
        pass
    elif hasattr(campaign, 'mailchimp_segment_tag') and campaign.mailchimp_segment_tag:
        segment_opts = mailchimp_service.build_tag_segment_opts(campaign.mailchimp_segment_tag)

    mc_campaign_id = await mailchimp_service.create_mc_campaign(
        list_id=audience_id,
        subject=campaign.subject,
        from_name=from_name,
        reply_to=reply_to,
        title=campaign.name,
        preview_text=campaign.preview_text or "",
        tracking_opens=data.tracking_opens,
        tracking_html_clicks=data.tracking_html_clicks,
        google_analytics_tag=data.google_analytics_tag,
        segment_opts=segment_opts,
        mc_segment_id=mc_segment_id,
    )

    # Step 5: Set content
    await mailchimp_service.set_campaign_content(
        mc_campaign_id=mc_campaign_id,
        html=campaign.body_html,
        plain_text=campaign.body_text or "",
    )

    # Step 6: Update our record
    campaign.mailchimp_campaign_id = mc_campaign_id
    campaign.mailchimp_audience_id = audience_id
    campaign.mailchimp_status = "draft"
    campaign.recipient_count = len(eligible)
    if mc_segment_id:
        campaign.mc_segment_id_combined = mc_segment_id
    if data.campaign_list_ids:
        campaign.segment_ids = data.campaign_list_ids
    db.commit()

    return {
        "mailchimp_campaign_id": mc_campaign_id,
        "mailchimp_audience_id": audience_id,
        "synced_count": result["added"] + result["updated"],
        "error_count": result["errors"],
        "recipient_count": len(eligible),
        "mc_segment_id": mc_segment_id,
    }


@router.get("/{campaign_id}/mailchimp-checklist")
async def mailchimp_send_checklist(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get Mailchimp's send checklist — validates campaign is ready to send."""
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not campaign or not campaign.mailchimp_campaign_id:
        raise HTTPException(status_code=400, detail="Campaign not synced to Mailchimp yet.")
    return await mailchimp_service.get_send_checklist(campaign.mailchimp_campaign_id)


@router.post("/{campaign_id}/send-test")
@limiter.limit("10/minute")
async def send_test_email_endpoint(
    request: Request,
    campaign_id: UUID,
    data: TestSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a test version of the campaign to specified email addresses."""
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if not campaign.mailchimp_campaign_id:
        raise HTTPException(status_code=400, detail="Sync campaign to Mailchimp before sending a test.")

    await mailchimp_service.send_test_email(
        mc_campaign_id=campaign.mailchimp_campaign_id,
        test_emails=data.test_emails,
        send_type=data.send_type or "html",
    )
    return {"sent": True, "test_emails": data.test_emails}


@router.post("/{campaign_id}/send-mailchimp")
@limiter.limit("10/minute")
async def send_via_mailchimp(
    request: Request,
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if not campaign.mailchimp_campaign_id:
        raise HTTPException(status_code=400, detail="Campaign has not been synced to Mailchimp yet.")

    await mailchimp_service.send_mc_campaign(campaign.mailchimp_campaign_id)
    campaign.mailchimp_status = "sending"
    campaign.status = "sending"
    campaign.sent_at = datetime.now(timezone.utc)
    db.commit()

    return {"sent": True, "mailchimp_campaign_id": campaign.mailchimp_campaign_id}


@router.post("/{campaign_id}/schedule-mailchimp")
@limiter.limit("10/minute")
async def schedule_via_mailchimp(
    request: Request,
    campaign_id: UUID,
    data: MailchimpScheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """Schedule the Mailchimp campaign to send at a specific time."""
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not campaign or not campaign.mailchimp_campaign_id:
        raise HTTPException(status_code=400, detail="Sync campaign to Mailchimp first.")

    await mailchimp_service.schedule_mc_campaign(
        mc_campaign_id=campaign.mailchimp_campaign_id,
        schedule_time=data.schedule_time,
    )
    campaign.mailchimp_status = "scheduled"
    campaign.scheduled_at = datetime.fromisoformat(data.schedule_time)
    campaign.status = "scheduled"
    db.commit()
    return {"scheduled": True, "schedule_time": data.schedule_time}


@router.get("/{campaign_id}/mailchimp-stats")
async def mailchimp_stats(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if not campaign.mailchimp_campaign_id:
        raise HTTPException(status_code=400, detail="Campaign has no Mailchimp integration.")

    stats = await mailchimp_service.get_mc_campaign_stats(campaign.mailchimp_campaign_id)
    return stats


@router.delete("/{campaign_id}/contacts/{contact_id}")
@limiter.limit("30/minute")
def remove_contact_from_campaign(
    request: Request,
    campaign_id: UUID,
    contact_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """Remove a contact from a campaign."""
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Check if contact is in campaign
    email_send = db.query(EmailSend).filter(
        EmailSend.campaign_id == campaign_id,
        EmailSend.contact_id == contact_id
    ).first()
    
    if not email_send:
        raise HTTPException(status_code=404, detail="Contact not found in this campaign")

    # Delete the email send record
    db.delete(email_send)
    
    # Update campaign stats if needed
    if email_send.status != "queued":
        # Adjust counters based on status
        if email_send.delivered_at:
            campaign.delivered_count = max(0, campaign.delivered_count - 1)
        if email_send.first_opened_at:
            campaign.unique_opens = max(0, campaign.unique_opens - 1)
            campaign.open_count = max(0, campaign.open_count - email_send.open_count)
        if email_send.first_clicked_at:
            campaign.unique_clicks = max(0, campaign.unique_clicks - 1)
            campaign.click_count = max(0, campaign.click_count - email_send.click_count)
        if email_send.bounced_at:
            campaign.bounce_count = max(0, campaign.bounce_count - 1)
        if email_send.unsubscribed_at:
            campaign.unsubscribe_count = max(0, campaign.unsubscribe_count - 1)
    
    campaign.sent_count = max(0, campaign.sent_count - 1)
    campaign.recipient_count = max(0, campaign.recipient_count - 1)
    
    db.commit()
    return {"message": "Contact removed from campaign", "campaign_id": str(campaign_id), "contact_id": str(contact_id)}


# ── Recipient Preview ──────────────────────────────────────────────────────

from app.schemas.campaign import (
    RecipientPreviewRequest,
    RecipientPreviewResponse,
    RecipientPreviewData,
    ContactPreview,
    ExclusionBreakdown,
    RecipientBreakdown,
)
from app.models.contact import Contact
from app.models.campaign_segment import CampaignSegment
from app.models.tag import Tag, ContactTag
from sqlalchemy import or_, and_, distinct, union_all, intersect


@router.post("/preview-recipients", response_model=RecipientPreviewResponse)
@limiter.limit("10/minute")
def preview_campaign_recipients(
    request: Request,
    payload: RecipientPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Preview campaign recipients with SQL UNION-based queries.
    
    Performance optimized for 30k+ contacts:
    - Single SQL query execution using UNION/INTERSECT
    - Database-level deduplication
    - No Python set operations on large datasets
    - Pagination and search support
    """
    from sqlalchemy import union, intersect, func, or_, case, literal_column
    from app.services import campaign_list_service
    from math import ceil
    
    # Empty response for no filters
    if not payload.list_ids and not payload.tag_ids:
        return RecipientPreviewResponse(
            data=RecipientPreviewData(
                total_matching=0,
                exclusions=ExclusionBreakdown(
                    unsubscribed=0, bounced=0, invalid_email=0, no_email=0, total=0
                ),
                final_count=0,
                page=payload.page,
                per_page=payload.per_page,
                total_pages=0,
                sample_contacts=[],
                breakdown=RecipientBreakdown(from_lists=0, from_tags=0, overlap=0),
            )
        )
    
    # Build subquery for contacts from Lists (CampaignSegments)
    list_subqueries = []
    list_name_mapping = {}  # segment_id -> name
    
    if payload.list_ids:
        for seg_id in payload.list_ids:
            segment = db.query(CampaignSegment).filter(CampaignSegment.id == seg_id).first()
            if segment:
                list_name_mapping[seg_id] = segment.name
                # Resolve segment contacts and create subquery
                contacts = campaign_list_service.resolve_segment_contacts(segment, db)
                contact_ids = [c.id for c in contacts]
                if contact_ids:
                    # Create subquery that returns contact_id and source
                    subq = (
                        db.query(
                            Contact.id.label('contact_id'),
                            literal_column(f"'{segment.name}'").label('source_name'),
                            literal_column("'list'").label('source_type')
                        )
                        .filter(Contact.id.in_(contact_ids))
                        .filter(Contact.deleted_at.is_(None))
                    )
                    list_subqueries.append(subq)
    
    # Build subquery for contacts from Tags
    tag_subquery = None
    if payload.tag_ids:
        # Get tag names for mapping
        tags = db.query(Tag).filter(Tag.id.in_(payload.tag_ids)).all()
        tag_names = {tag.id: tag.name for tag in tags}
        
        # Create subquery with tag source attribution
        tag_subquery = (
            db.query(
                Contact.id.label('contact_id'),
                Tag.name.label('source_name'),
                literal_column("'tag'").label('source_type')
            )
            .join(Contact.tags)
            .filter(Tag.id.in_(payload.tag_ids))
            .filter(Contact.deleted_at.is_(None))
        )
    
    # Combine all subqueries with UNION
    all_subqueries = []
    if list_subqueries:
        all_subqueries.extend(list_subqueries)
    if tag_subquery:
        all_subqueries.append(tag_subquery)
    
    if not all_subqueries:
        return RecipientPreviewResponse(
            data=RecipientPreviewData(
                total_matching=0,
                exclusions=ExclusionBreakdown(
                    unsubscribed=0, bounced=0, invalid_email=0, no_email=0, total=0
                ),
                final_count=0,
                page=payload.page,
                per_page=payload.per_page,
                total_pages=0,
                sample_contacts=[],
                breakdown=RecipientBreakdown(from_lists=0, from_tags=0, overlap=0),
            )
        )
    
    # Union all sources
    combined_sources = union(*all_subqueries).alias('combined_sources')
    
    # For breakdown: count unique contacts from lists vs tags
    from_lists_count = 0
    from_tags_count = 0
    
    if payload.list_ids and list_subqueries:
        from_lists_count = (
            db.query(func.count(func.distinct(combined_sources.c.contact_id)))
            .filter(combined_sources.c.source_type == 'list')
            .scalar() or 0
        )
    
    if payload.tag_ids:
        from_tags_count = (
            db.query(func.count(func.distinct(combined_sources.c.contact_id)))
            .filter(combined_sources.c.source_type == 'tag')
            .scalar() or 0
        )
    
    # Get unique contact IDs (for combine_mode logic)
    if payload.combine_mode == "all" and payload.list_ids and payload.tag_ids:
        # AND mode: only contacts that appear in BOTH lists AND tags
        # Count how many source types each contact appears in
        contact_source_counts = (
            db.query(
                combined_sources.c.contact_id,
                func.count(func.distinct(combined_sources.c.source_type)).label('source_type_count')
            )
            .group_by(combined_sources.c.contact_id)
            .subquery()
        )
        
        # Only include contacts with both source types
        combined_contact_ids = (
            db.query(contact_source_counts.c.contact_id.label('id'))
            .filter(contact_source_counts.c.source_type_count == 2)
        )
    else:
        # OR mode: any contact from any source
        # FIX: Explicitly label the column as 'id'
        combined_contact_ids = (
            db.query(func.distinct(combined_sources.c.contact_id).label('id'))
        )
    
    # Materialize as CTE for counting
    combined_ids_cte = combined_contact_ids.cte('combined_ids')
    
    # Count total matching
    # FIX: Use 'id' instead of 'contact_id'
    total_matching = db.query(func.count(combined_ids_cte.c.id)).scalar() or 0
    
    # Calculate overlap
    overlap = from_lists_count + from_tags_count - total_matching if from_lists_count and from_tags_count else 0
    
    # Count DNC exclusions with single query
    exclusion_counts = {
        "unsubscribed": 0,
        "bounced": 0,
        "invalid_email": 0,
        "no_email": 0,
    }
    
    if payload.exclude_dnc and total_matching > 0:
        exclusions = (
            db.query(
                func.sum(case((Contact.email_unsubscribed == True, 1), else_=0)).label('unsubscribed'),
                func.sum(case((Contact.email_bounced == True, 1), else_=0)).label('bounced'),
                func.sum(case((Contact.email_valid == False, 1), else_=0)).label('invalid_email'),
                func.sum(case((Contact._email_encrypted.is_(None), 1), else_=0)).label('no_email'),
            )
            .filter(Contact.id.in_(db.query(combined_ids_cte.c.id)))
            .filter(Contact.deleted_at.is_(None))
            .first()
        )
        
        if exclusions:
            exclusion_counts["unsubscribed"] = exclusions.unsubscribed or 0
            exclusion_counts["bounced"] = exclusions.bounced or 0
            exclusion_counts["invalid_email"] = exclusions.invalid_email or 0
            exclusion_counts["no_email"] = exclusions.no_email or 0
    
    exclusion_counts["total"] = sum(exclusion_counts.values())
    
    # Build final query with DNC filters
    final_query = (
        db.query(Contact)
        .filter(Contact.id.in_(db.query(combined_ids_cte.c.id)))
        .filter(Contact.deleted_at.is_(None))
    )
    
    if payload.exclude_dnc:
        final_query = final_query.filter(
            Contact.email_unsubscribed == False,
            Contact.email_bounced == False,
            Contact.email_valid == True,
            Contact._email_encrypted.isnot(None),
        )
    
    # Add search filter if provided
    if payload.search:
        search_term = f"%{payload.search}%"
        final_query = final_query.filter(
            or_(
                Contact.first_name.ilike(search_term),
                Contact.last_name.ilike(search_term),
                Contact.company.ilike(search_term),
                # Email search - only if encrypted field supports it
                # Contact._email_encrypted.ilike(search_term),  # May not work with encryption
            )
        )
    
    # Get total count after all filters
    final_count = final_query.count()
    
    # Calculate pagination
    total_pages = ceil(final_count / payload.per_page) if final_count > 0 else 0
    offset = (payload.page - 1) * payload.per_page
    
    # Get paginated results (not just sample, but full page)
    paginated_contacts = (
        final_query
        .order_by(Contact.last_name.nulls_last(), Contact.first_name.nulls_last())
        .offset(offset)
        .limit(payload.per_page)
        .all()
    )
    
    # Build source attribution for contacts
    sample_contacts = []
    for c in paginated_contacts:
        # Get all sources for this contact
        sources_query = (
            db.query(combined_sources.c.source_name)
            .filter(combined_sources.c.contact_id == c.id)
            .distinct()
        )
        sources = [row.source_name for row in sources_query.all()]
        
        sample_contacts.append(ContactPreview(
            id=c.id,
            full_name=c.full_name,
            email=c.email,
            company=c.company,
            sources=sources,
        ))
    
    return RecipientPreviewResponse(
        data=RecipientPreviewData(
            total_matching=total_matching,
            exclusions=ExclusionBreakdown(
                unsubscribed=exclusion_counts["unsubscribed"],
                bounced=exclusion_counts["bounced"],
                invalid_email=exclusion_counts["invalid_email"],
                no_email=exclusion_counts["no_email"],
                total=exclusion_counts["total"],
            ),
            final_count=final_count,
            page=payload.page,
            per_page=payload.per_page,
            total_pages=total_pages,
            sample_contacts=sample_contacts,
            breakdown=RecipientBreakdown(
                from_lists=from_lists_count,
                from_tags=from_tags_count,
                overlap=overlap,
            ),
        )
    )

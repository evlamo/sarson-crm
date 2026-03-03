"""
Campaigns API — CRUD, send, schedule, cancel, stats, recipients.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user, require_not_restricted, get_admin_user
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
from app.services import audit_service

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])

# Rate limiter — uses app.state.limiter set in main.py
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)


def _capture_campaign_snapshot(campaign: EmailCampaign) -> dict:
    """Capture current values for audit comparison."""
    return {
        "name": campaign.name,
        "subject": campaign.subject,
        "status": campaign.status,
        "from_name": campaign.from_name,
        "from_email": campaign.from_email,
        "segment_id": str(campaign.segment_id) if campaign.segment_id else None,
    }


# ── List Campaigns ─────────────────────────────────────────────────────────

@router.get("", response_model=CampaignListOut)
def list_campaigns(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(EmailCampaign)
    if status:
        query = query.filter(EmailCampaign.status == status)

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
    
    # Audit: campaign created
    audit_service.log_action_sync(
        db=db,
        action="campaign.create",
        entity_type="campaign",
        entity_id=str(campaign.id),
        new_values=_capture_campaign_snapshot(campaign),
        user_id=str(current_user.id),
    )
    db.commit()
    
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

    old_snapshot = _capture_campaign_snapshot(campaign)

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(campaign, key, value)

    campaign.updated_at = datetime.now(timezone.utc)
    
    new_snapshot = _capture_campaign_snapshot(campaign)
    changes = {k: v for k, v in new_snapshot.items() if old_snapshot.get(k) != v}
    
    if changes:
        audit_service.log_action_sync(
            db=db,
            action="campaign.update",
            entity_type="campaign",
            entity_id=str(campaign.id),
            old_values={k: old_snapshot[k] for k in changes},
            new_values=changes,
            user_id=str(current_user.id),
        )
    
    db.commit()
    db.refresh(campaign)
    return campaign


# ── Delete Campaign ────────────────────────────────────────────────────────

@router.delete("/{campaign_id}", status_code=204)
def delete_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_not_restricted),
):
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.status != "draft":
        raise HTTPException(status_code=400, detail="Can only delete draft campaigns")

    # Audit: campaign deleted
    audit_service.log_action_sync(
        db=db,
        action="campaign.delete",
        entity_type="campaign",
        entity_id=str(campaign.id),
        old_values=_capture_campaign_snapshot(campaign),
        user_id=str(current_user.id),
    )

    db.delete(campaign)
    db.commit()


# ── Send Campaign ──────────────────────────────────────────────────────────

@router.post("/{campaign_id}/send")
def send_campaign(
    campaign_id: UUID,
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

    old_status = campaign.status
    
    # Audit: campaign send initiated
    audit_service.log_action_sync(
        db=db,
        action="campaign.send",
        entity_type="campaign",
        entity_id=str(campaign.id),
        old_values={"status": old_status},
        new_values={"status": "sending"},
        user_id=str(current_user.id),
    )
    db.commit()

    # Queue the Celery task
    task = send_campaign_task.delay(str(campaign.id))

    return {
        "message": "Campaign queued for sending",
        "campaign_id": str(campaign.id),
        "task_id": task.id,
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

    old_status = campaign.status
    campaign.scheduled_at = data.scheduled_at
    campaign.status = "scheduled"
    
    # Audit: campaign scheduled
    audit_service.log_action_sync(
        db=db,
        action="campaign.schedule",
        entity_type="campaign",
        entity_id=str(campaign.id),
        old_values={"status": old_status, "scheduled_at": None},
        new_values={"status": "scheduled", "scheduled_at": data.scheduled_at.isoformat()},
        user_id=str(current_user.id),
    )
    
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

    old_status = campaign.status
    
    # Audit: campaign cancelled
    audit_service.log_action_sync(
        db=db,
        action="campaign.cancel",
        entity_type="campaign",
        entity_id=str(campaign.id),
        old_values={"status": old_status},
        new_values={"status": "cancelled"},
        user_id=str(current_user.id),
    )
    db.commit()

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
    
    # Audit: campaign duplicated
    audit_service.log_action_sync(
        db=db,
        action="campaign.duplicate",
        entity_type="campaign",
        entity_id=str(clone.id),
        new_values={
            "name": clone.name,
            "cloned_from": str(original.id),
        },
        user_id=str(current_user.id),
    )
    db.commit()
    
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

    # Filter out unsubscribed/bounced/master_dnc and (if linked to sales campaign) done contacts
    sales_campaign_id_str = str(campaign.sales_campaign_id) if campaign.sales_campaign_id else None
    eligible = mailchimp_service.filter_eligible_contacts(db, list(contact_ids), sales_campaign_id_str)
    if not eligible:
        raise HTTPException(status_code=400, detail="No eligible contacts after filtering unsubscribed/bounced/DNC.")

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
    
    # Audit: Mailchimp sync
    audit_service.log_action_sync(
        db=db,
        action="campaign.mailchimp_sync",
        entity_type="campaign",
        entity_id=str(campaign.id),
        new_values={
            "mailchimp_campaign_id": mc_campaign_id,
            "synced_count": result["added"] + result["updated"],
            "recipient_count": len(eligible),
        },
        user_id=str(current_user.id),
    )
    
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
    
    # Audit: test email sent
    audit_service.log_action_sync(
        db=db,
        action="campaign.send_test",
        entity_type="campaign",
        entity_id=str(campaign.id),
        new_values={"test_emails": data.test_emails},
        user_id=str(current_user.id),
    )
    db.commit()
    
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

    old_status = campaign.status
    
    await mailchimp_service.send_mc_campaign(campaign.mailchimp_campaign_id)
    campaign.mailchimp_status = "sending"
    campaign.status = "sending"
    campaign.sent_at = datetime.now(timezone.utc)
    
    # Audit: campaign sent via Mailchimp
    audit_service.log_action_sync(
        db=db,
        action="campaign.mailchimp_send",
        entity_type="campaign",
        entity_id=str(campaign.id),
        old_values={"status": old_status},
        new_values={"status": "sending", "mailchimp_status": "sending"},
        user_id=str(current_user.id),
    )
    
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

    old_status = campaign.status
    
    await mailchimp_service.schedule_mc_campaign(
        mc_campaign_id=campaign.mailchimp_campaign_id,
        schedule_time=data.schedule_time,
    )
    campaign.mailchimp_status = "scheduled"
    campaign.scheduled_at = datetime.fromisoformat(data.schedule_time)
    campaign.status = "scheduled"
    
    # Audit: campaign scheduled via Mailchimp
    audit_service.log_action_sync(
        db=db,
        action="campaign.mailchimp_schedule",
        entity_type="campaign",
        entity_id=str(campaign.id),
        old_values={"status": old_status},
        new_values={"status": "scheduled", "scheduled_at": data.schedule_time},
        user_id=str(current_user.id),
    )
    
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

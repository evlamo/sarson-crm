"""
Campaigns API — CRUD, send, schedule, cancel, stats, recipients.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, desc
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
)
from app.services.campaign_service import get_campaign_stats
from app.tasks.send_campaign import send_campaign_task, cancel_campaign_task

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])


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

from pydantic import BaseModel as _BaseModel
from typing import List as _List
from app.services import mailchimp_service
from app.models.contact import Contact
from app.models.segment import Segment as SegmentModel


class MailchimpSyncRequest(_BaseModel):
    contact_ids: Optional[_List[str]] = None
    segment_id: Optional[str] = None
    tag_ids: Optional[_List[str]] = None


@router.post("/{campaign_id}/sync-mailchimp")
async def sync_to_mailchimp(
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
        from app.models.tag import contact_tags
        from sqlalchemy import select
        stmt = select(contact_tags.c.contact_id).where(
            contact_tags.c.tag_id.in_(data.tag_ids)
        )
        rows = db.execute(stmt).fetchall()
        contact_ids.update(str(r[0]) for r in rows)

    if not contact_ids:
        raise HTTPException(status_code=400, detail="No contacts specified. Provide contact_ids, segment_id, or tag_ids.")

    # Filter out unsubscribed/bounced
    eligible = mailchimp_service.filter_eligible_contacts(db, list(contact_ids))
    if not eligible:
        raise HTTPException(status_code=400, detail="No eligible contacts after filtering unsubscribed/bounced.")

    # Step 1: Get or create audience
    from_name = campaign.from_name or "Sarson Funds"
    reply_to = campaign.reply_to or campaign.from_email
    audience_id = await mailchimp_service.get_or_create_audience(
        name=f"CRM - {campaign.name}",
        from_name=from_name,
        reply_to=reply_to,
    )

    # Step 2: Batch upsert members
    result = await mailchimp_service.batch_upsert_members(audience_id, eligible)

    # Step 3: Create Mailchimp campaign
    mc_campaign_id = await mailchimp_service.create_campaign(
        list_id=audience_id,
        subject=campaign.subject,
        from_name=from_name,
        reply_to=reply_to,
        title=campaign.name,
    )

    # Step 4: Set content
    await mailchimp_service.set_campaign_content(
        campaign_id=mc_campaign_id,
        html=campaign.body_html,
        plain_text=campaign.body_text,
    )

    # Step 5: Update our record
    campaign.mailchimp_campaign_id = mc_campaign_id
    campaign.mailchimp_audience_id = audience_id
    campaign.mailchimp_status = "draft"
    db.commit()

    return {
        "mailchimp_campaign_id": mc_campaign_id,
        "mailchimp_audience_id": audience_id,
        "synced_count": result["added"] + result["updated"],
        "error_count": result["errors"],
    }


@router.post("/{campaign_id}/send-mailchimp")
async def send_via_mailchimp(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if not campaign.mailchimp_campaign_id:
        raise HTTPException(status_code=400, detail="Campaign has not been synced to Mailchimp yet.")

    await mailchimp_service.send_campaign(campaign.mailchimp_campaign_id)
    campaign.mailchimp_status = "sending"
    db.commit()

    return {"sent": True, "mailchimp_campaign_id": campaign.mailchimp_campaign_id}


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

    stats = await mailchimp_service.get_campaign_stats(campaign.mailchimp_campaign_id)
    return stats

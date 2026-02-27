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
from app.auth.dependencies import get_current_user
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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

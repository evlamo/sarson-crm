"""
Campaign Lists router — manages CampaignSegments (called "Lists" in the frontend UI).
Prefix: /api/v1/campaign-lists
"""
import logging
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_not_restricted
from app.database import get_db
from app.models.campaign_segment import CampaignSegment
from app.models.user import User
from app.schemas.campaign_segment import (
    CampaignSegmentCreate,
    CampaignSegmentUpdate,
    CampaignSegmentResponse,
    CampaignSegmentPreviewResponse,
    CombinePreviewRequest,
    CombineSyncRequest,
)
from app.services import campaign_list_service
from app.services import mailchimp_service
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/campaign-lists", tags=["campaign-lists"])
limiter = Limiter(key_func=get_remote_address)


@router.get("", response_model=List[CampaignSegmentResponse])
def list_campaign_segments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
):
    return (
        db.query(CampaignSegment)
        .order_by(CampaignSegment.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.post("", response_model=CampaignSegmentResponse, status_code=201)
def create_campaign_segment(
    data: CampaignSegmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    segment = CampaignSegment(
        name=data.name,
        description=data.description,
        filters=data.filters.model_dump(mode="json") if data.filters else {},
        contact_ids=[cid for cid in (data.contact_ids or [])],
        created_by=current_user.id,
    )
    db.add(segment)
    db.flush()

    contacts = campaign_list_service.resolve_segment_contacts(segment, db)
    segment.member_count = len(contacts)
    db.commit()
    db.refresh(segment)
    return segment


## FIX C1: Static path endpoints BEFORE /{segment_id} to prevent UUID matching
@router.post("/combine/preview")
def preview_combined(
    data: CombinePreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview combined contact count for multiple lists."""
    contacts = campaign_list_service.resolve_combined_segment_contacts(data.segment_ids, db)
    return {"count": len(contacts), "segment_ids": [str(sid) for sid in data.segment_ids]}


@router.post("/combine/sync")
@limiter.limit("10/minute")
async def sync_combined_to_mailchimp(
    request: Request,
    data: CombineSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Combine multiple lists and sync as a single Mailchimp static segment."""
    if not data.segment_ids:
        raise HTTPException(status_code=400, detail="No list IDs provided")

    contacts = campaign_list_service.resolve_combined_segment_contacts(data.segment_ids, db)
    if not contacts:
        raise HTTPException(status_code=400, detail="No eligible contacts across selected lists")

    audience_id = await mailchimp_service.get_main_audience_id()

    members = [
        {
            "email": c.email,
            "first_name": c.first_name or "",
            "last_name": c.last_name or "",
            "phone": c.phone or "",
            "company": c.company or "",
        }
        for c in contacts
    ]
    await mailchimp_service.batch_upsert_members(audience_id, members)

    emails = [c.email for c in contacts if c.email]
    mc_seg_id = await mailchimp_service.create_or_update_static_segment(
        list_id=audience_id,
        segment_name=f"{data.campaign_name} - Combined",
        emails=emails,
        existing_mc_segment_id=None,
    )

    return {"mc_segment_id": mc_seg_id, "member_count": len(contacts)}


@router.post("/preview-filters")
def preview_filters(
    data: CampaignSegmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview contact count for a filter definition before saving."""
    temp_segment = CampaignSegment(
        name="temp",
        filters=data.filters.model_dump(mode="json") if data.filters else {},
        contact_ids=[str(cid) for cid in (data.contact_ids or [])],
    )
    contacts = campaign_list_service.resolve_segment_contacts(temp_segment, db)
    return {"count": len(contacts)}


@router.get("/{segment_id}", response_model=CampaignSegmentResponse)
def get_campaign_segment(
    segment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seg = db.query(CampaignSegment).filter(CampaignSegment.id == segment_id).first()
    if not seg:
        raise HTTPException(status_code=404, detail="List not found")
    return seg


@router.patch("/{segment_id}", response_model=CampaignSegmentResponse)
def update_campaign_segment(
    segment_id: UUID,
    data: CampaignSegmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seg = db.query(CampaignSegment).filter(CampaignSegment.id == segment_id).first()
    if not seg:
        raise HTTPException(status_code=404, detail="List not found")
    if data.name is not None:
        seg.name = data.name
    if data.description is not None:
        seg.description = data.description
    if data.filters is not None:
        seg.filters = data.filters.model_dump(mode="json")
    if data.contact_ids is not None:
        seg.contact_ids = [cid for cid in data.contact_ids]
    seg.updated_at = datetime.now(timezone.utc)

    contacts = campaign_list_service.resolve_segment_contacts(seg, db)
    seg.member_count = len(contacts)
    db.commit()
    db.refresh(seg)
    return seg


@router.delete("/{segment_id}", status_code=204)
def delete_campaign_segment(
    segment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_not_restricted),
):
    seg = db.query(CampaignSegment).filter(CampaignSegment.id == segment_id).first()
    if not seg:
        raise HTTPException(status_code=404, detail="List not found")

    # FIX H3: Orphan check — prevent deleting lists used by campaigns
    from sqlalchemy import text
    result = db.execute(
        text("SELECT id, name FROM email_campaigns WHERE :seg_id = ANY(segment_ids) LIMIT 5"),
        {"seg_id": str(segment_id)}
    ).fetchall()
    if result:
        campaign_names = ", ".join([r[1] for r in result[:3]])
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: this list is used by {len(result)} campaign(s): {campaign_names}"
        )

    db.delete(seg)
    db.commit()


@router.get("/{segment_id}/members")
def get_segment_members(
    segment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    search: str = "",
    page: int = 1,
    per_page: int = 50,
):
    """Return paginated, searchable list of resolved contacts for a list, with source tag."""
    from app.models.contact import Contact as ContactModel

    seg = db.query(CampaignSegment).filter(CampaignSegment.id == segment_id).first()
    if not seg:
        raise HTTPException(status_code=404, detail="List not found")

    contacts = campaign_list_service.resolve_segment_contacts(seg, db)
    manual_ids = {str(cid) for cid in (seg.contact_ids or [])}

    # Apply search filter
    if search:
        s = search.lower()
        contacts = [
            c for c in contacts
            if s in (c.first_name or "").lower()
            or s in (c.last_name or "").lower()
            or s in (c.email or "").lower()
            or s in (c.company or "").lower()
        ]

    total = len(contacts)
    start = (page - 1) * per_page
    page_contacts = contacts[start: start + per_page]

    data = [
        {
            "id": str(c.id),
            "first_name": c.first_name,
            "last_name": c.last_name,
            "email": c.email,
            "company": c.company,
            "status": c.status,
            "source": "manual" if str(c.id) in manual_ids else "filter",
        }
        for c in page_contacts
    ]

    return {"data": data, "total": total, "page": page, "per_page": per_page}


@router.get("/{segment_id}/preview", response_model=CampaignSegmentPreviewResponse)
def preview_campaign_segment(
    segment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seg = db.query(CampaignSegment).filter(CampaignSegment.id == segment_id).first()
    if not seg:
        raise HTTPException(status_code=404, detail="List not found")
    return campaign_list_service.get_segment_preview(seg, db)


@router.post("/{segment_id}/sync")
@limiter.limit("10/minute")
async def sync_to_mailchimp(
    request: Request,
    segment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sync a CRM list to Mailchimp as a static segment."""
    seg = db.query(CampaignSegment).filter(CampaignSegment.id == segment_id).first()
    if not seg:
        raise HTTPException(status_code=404, detail="List not found")

    contacts = campaign_list_service.resolve_segment_contacts(seg, db)
    if not contacts:
        raise HTTPException(status_code=400, detail="No eligible contacts in this list")

    audience_id = await mailchimp_service.get_main_audience_id()

    members = [
        {
            "email": c.email,
            "first_name": c.first_name or "",
            "last_name": c.last_name or "",
            "phone": c.phone or "",
            "company": c.company or "",
        }
        for c in contacts
    ]
    await mailchimp_service.batch_upsert_members(audience_id, members)

    emails = [c.email for c in contacts if c.email]
    mc_seg_id = await mailchimp_service.create_or_update_static_segment(
        list_id=audience_id,
        segment_name=seg.name,
        emails=emails,
        existing_mc_segment_id=seg.mc_segment_id,
    )

    seg.mc_segment_id = mc_seg_id
    seg.mc_synced_at = datetime.now(timezone.utc)
    seg.member_count = len(contacts)
    db.commit()

    return {
        "mc_segment_id": mc_seg_id,
        "member_count": len(contacts),
        "synced_at": seg.mc_synced_at,
    }




"""Deals API — CRUD + stage moves for pipeline Kanban."""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.deal import Deal
from app.models.company import Company
from app.utils.time import utcnow
from app.services import audit_service

router = APIRouter(prefix="/api/v1/deals", tags=["deals"])


# ── Schemas ────────────────────────────────────────────────────────────────

class DealCreate(BaseModel):
    title: str
    description: Optional[str] = None
    stage: str = "sourced"
    amount: Optional[float] = None
    currency: str = "USD"
    expected_close: Optional[str] = None
    company_id: Optional[UUID] = None
    deal_type: Optional[str] = None


class DealUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    stage: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    expected_close: Optional[str] = None
    company_id: Optional[UUID] = None
    deal_type: Optional[str] = None


class StageUpdate(BaseModel):
    stage: str


class DealOut(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    stage: str
    amount: Optional[float]
    currency: str
    expected_close: Optional[str]
    company_id: Optional[UUID]
    owner_id: Optional[UUID]
    company_name: Optional[str] = None
    deal_type: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


def _capture_deal_snapshot(deal: Deal) -> dict:
    """Capture current values of a deal for audit comparison."""
    return {
        "title": deal.title,
        "description": deal.description,
        "stage": deal.stage,
        "amount": float(deal.amount) if deal.amount else None,
        "currency": deal.currency,
        "expected_close": str(deal.expected_close) if deal.expected_close else None,
        "company_id": str(deal.company_id) if deal.company_id else None,
        "deal_type": deal.deal_type,
    }


def _compute_changes(old: dict, new: dict) -> dict:
    changes = {}
    for key in set(old.keys()) | set(new.keys()):
        old_val = old.get(key)
        new_val = new.get(key)
        if old_val != new_val:
            changes[key] = {"old": old_val, "new": new_val}
    return changes


def _enrich(deal: Deal) -> dict:
    d = DealOut.model_validate(deal).model_dump()
    if deal.company:
        d["company_name"] = deal.company.name
    d["expected_close"] = str(deal.expected_close) if deal.expected_close else None
    d["amount"] = float(deal.amount) if deal.amount else None
    return d


# ── List Deals ─────────────────────────────────────────────────────────────

@router.get("")
def list_deals(
    stage: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        db.query(Deal)
        .options(joinedload(Deal.company))
        .filter(Deal.deleted_at.is_(None))
    )
    if stage:
        query = query.filter(Deal.stage == stage)

    total = db.query(func.count(Deal.id)).filter(
        Deal.deleted_at.is_(None),
        *([Deal.stage == stage] if stage else []),
    ).scalar()

    deals = query.order_by(Deal.created_at.desc()).offset(skip).limit(limit).all()
    return {
        "data": [_enrich(d) for d in deals],
        "total": total,
        "page": skip // limit + 1 if limit else 1,
        "per_page": limit,
    }


# ── Create Deal ────────────────────────────────────────────────────────────

@router.post("", status_code=201)
def create_deal(
    data: DealCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = Deal(
        title=data.title,
        description=data.description,
        stage=data.stage,
        amount=data.amount,
        currency=data.currency,
        expected_close=data.expected_close,
        company_id=data.company_id,
        deal_type=data.deal_type,
        owner_id=current_user.id,
        created_by=current_user.id,
    )
    db.add(deal)
    db.commit()
    db.refresh(deal)
    
    # Audit: deal created
    audit_service.log_action_sync(
        db=db,
        action="deal.create",
        entity_type="deal",
        entity_id=str(deal.id),
        new_values=_capture_deal_snapshot(deal),
        user_id=str(current_user.id),
    )
    db.commit()
    
    # Reload with company relationship
    deal = db.query(Deal).options(joinedload(Deal.company)).filter(Deal.id == deal.id).first()
    return _enrich(deal)


# ── Get Deal ───────────────────────────────────────────────────────────────

@router.get("/{deal_id}")
def get_deal(
    deal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = (
        db.query(Deal)
        .options(joinedload(Deal.company))
        .filter(Deal.id == deal_id, Deal.deleted_at.is_(None))
        .first()
    )
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    return _enrich(deal)


# ── Update Deal ────────────────────────────────────────────────────────────

@router.patch("/{deal_id}")
def update_deal(
    deal_id: UUID,
    data: DealUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = db.query(Deal).filter(Deal.id == deal_id, Deal.deleted_at.is_(None)).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    old_snapshot = _capture_deal_snapshot(deal)

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(deal, key, value)
    deal.updated_at = utcnow()
    
    new_snapshot = _capture_deal_snapshot(deal)
    changes = _compute_changes(old_snapshot, new_snapshot)
    
    if changes:
        audit_service.log_action_sync(
            db=db,
            action="deal.update",
            entity_type="deal",
            entity_id=str(deal.id),
            old_values={k: v["old"] for k, v in changes.items()},
            new_values={k: v["new"] for k, v in changes.items()},
            user_id=str(current_user.id),
        )
    
    db.commit()
    db.refresh(deal)
    deal = db.query(Deal).options(joinedload(Deal.company)).filter(Deal.id == deal.id).first()
    return _enrich(deal)


# ── Move Stage ─────────────────────────────────────────────────────────────

@router.patch("/{deal_id}/stage")
def move_deal_stage(
    deal_id: UUID,
    data: StageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = db.query(Deal).filter(Deal.id == deal_id, Deal.deleted_at.is_(None)).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    old_stage = deal.stage
    deal.stage = data.stage
    deal.updated_at = utcnow()
    
    # Audit: stage change (important pipeline event)
    audit_service.log_action_sync(
        db=db,
        action="deal.stage_change",
        entity_type="deal",
        entity_id=str(deal.id),
        old_values={"stage": old_stage},
        new_values={"stage": data.stage},
        user_id=str(current_user.id),
    )
    
    db.commit()
    db.refresh(deal)
    deal = db.query(Deal).options(joinedload(Deal.company)).filter(Deal.id == deal.id).first()
    return _enrich(deal)


# ── Delete Deal ────────────────────────────────────────────────────────────

@router.delete("/{deal_id}", status_code=204)
def delete_deal(
    deal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = db.query(Deal).filter(Deal.id == deal_id, Deal.deleted_at.is_(None)).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    old_snapshot = _capture_deal_snapshot(deal)
    deal.deleted_at = utcnow()
    
    # Audit: deal deleted
    audit_service.log_action_sync(
        db=db,
        action="deal.delete",
        entity_type="deal",
        entity_id=str(deal.id),
        old_values=old_snapshot,
        user_id=str(current_user.id),
    )
    
    db.commit()

"""Deals API — CRUD + stage moves for pipeline Kanban."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.deal import Deal
from app.models.company import Company

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


def _enrich(deal: Deal, db: Session) -> dict:
    d = DealOut.model_validate(deal).model_dump()
    if deal.company_id:
        co = db.query(Company).filter(Company.id == deal.company_id).first()
        if co:
            d["company_name"] = co.name
    d["expected_close"] = str(deal.expected_close) if deal.expected_close else None
    d["amount"] = float(deal.amount) if deal.amount else None
    return d


# ── List Deals ─────────────────────────────────────────────────────────────

@router.get("")
def list_deals(
    stage: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Deal).filter(Deal.deleted_at.is_(None))
    if stage:
        query = query.filter(Deal.stage == stage)
    deals = query.order_by(Deal.created_at.desc()).all()
    return [_enrich(d, db) for d in deals]


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
    return _enrich(deal, db)


# ── Get Deal ───────────────────────────────────────────────────────────────

@router.get("/{deal_id}")
def get_deal(
    deal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = db.query(Deal).filter(Deal.id == deal_id, Deal.deleted_at.is_(None)).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    return _enrich(deal, db)


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

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(deal, key, value)
    deal.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(deal)
    return _enrich(deal, db)


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
    deal.stage = data.stage
    deal.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(deal)
    return _enrich(deal, db)


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
    deal.deleted_at = datetime.utcnow()
    db.commit()

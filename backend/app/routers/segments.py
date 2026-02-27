from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from datetime import datetime
import uuid

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.segment import Segment
from app.models.contact import Contact
from app.models.user import User
from app.schemas.segment import (
    SegmentCreate, SegmentUpdate, SegmentResponse,
    SegmentListResponse, SegmentContactsResponse,
)
from app.schemas.contact import ContactResponse
from app.services.segment_service import build_segment_query, count_segment_contacts

router = APIRouter(prefix="/api/v1/segments", tags=["segments"])


def _segment_response(segment: Segment, db: Session) -> SegmentResponse:
    count = count_segment_contacts(db, segment.filters)
    return SegmentResponse(
        id=segment.id,
        name=segment.name,
        description=segment.description,
        filter_rules=segment.filters,
        contact_count=count,
        created_by=segment.created_by,
        created_at=segment.created_at,
        updated_at=segment.updated_at,
    )


@router.get("", response_model=SegmentListResponse)
def list_segments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    segments = db.query(Segment).filter(Segment.is_dynamic == True).order_by(Segment.name).all()
    data = [_segment_response(s, db) for s in segments]
    return SegmentListResponse(data=data, total=len(data))


@router.get("/{segment_id}", response_model=SegmentResponse)
def get_segment(
    segment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    segment = db.query(Segment).filter(Segment.id == segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    return _segment_response(segment, db)


@router.post("", response_model=SegmentResponse, status_code=status.HTTP_201_CREATED)
def create_segment(
    payload: SegmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    segment = Segment(
        name=payload.name,
        description=payload.description,
        filters=payload.filter_rules.model_dump(),
        is_dynamic=True,
        created_by=current_user.id,
    )
    db.add(segment)
    db.commit()
    db.refresh(segment)
    return _segment_response(segment, db)


@router.put("/{segment_id}", response_model=SegmentResponse)
def update_segment(
    segment_id: uuid.UUID,
    payload: SegmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    segment = db.query(Segment).filter(Segment.id == segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    if payload.name is not None:
        segment.name = payload.name
    if payload.description is not None:
        segment.description = payload.description
    if payload.filter_rules is not None:
        segment.filters = payload.filter_rules.model_dump()

    segment.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(segment)
    return _segment_response(segment, db)


@router.delete("/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_segment(
    segment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    segment = db.query(Segment).filter(Segment.id == segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    db.delete(segment)
    db.commit()


@router.get("/{segment_id}/contacts", response_model=SegmentContactsResponse)
def get_segment_contacts(
    segment_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    segment = db.query(Segment).filter(Segment.id == segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    query = build_segment_query(db, segment.filters).options(
        joinedload(Contact.tags), joinedload(Contact.company_obj)
    )
    total = count_segment_contacts(db, segment.filters)
    contacts = (
        query.order_by(Contact.last_name.asc().nullslast())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    from app.routers.contacts import _build_response
    return SegmentContactsResponse(
        data=[_build_response(c).model_dump() for c in contacts],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{segment_id}/count")
def get_segment_count(
    segment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    segment = db.query(Segment).filter(Segment.id == segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    return {"segment_id": str(segment_id), "count": count_segment_contacts(db, segment.filters)}

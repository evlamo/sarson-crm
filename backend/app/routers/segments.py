from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from datetime import datetime
from app.utils.time import utcnow
import uuid

from app.database import get_db
from app.auth.dependencies import get_current_user, require_not_restricted
from app.models.segment import Segment
from app.models.contact import Contact
from app.models.user import User
from app.schemas.segment import (
    SegmentCreate, SegmentUpdate, SegmentResponse,
    SegmentListResponse, SegmentContactsResponse,
)
from app.schemas.contact import ContactResponse
from app.services.segment_service import build_segment_query, count_segment_contacts
from app.services import audit_service

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
    
    # Audit: segment created
    audit_service.log_action_sync(
        db=db,
        action="segment.create",
        entity_type="segment",
        entity_id=str(segment.id),
        new_values={
            "name": segment.name,
            "description": segment.description,
            "filters": segment.filters,
        },
        user_id=str(current_user.id),
    )
    db.commit()
    
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

    old_values = {
        "name": segment.name,
        "description": segment.description,
        "filters": segment.filters,
    }

    if payload.name is not None:
        segment.name = payload.name
    if payload.description is not None:
        segment.description = payload.description
    if payload.filter_rules is not None:
        segment.filters = payload.filter_rules.model_dump()

    segment.updated_at = utcnow()
    
    new_values = {
        "name": segment.name,
        "description": segment.description,
        "filters": segment.filters,
    }
    
    changes = {k: v for k, v in new_values.items() if old_values.get(k) != v}
    
    if changes:
        audit_service.log_action_sync(
            db=db,
            action="segment.update",
            entity_type="segment",
            entity_id=str(segment.id),
            old_values={k: old_values[k] for k in changes},
            new_values=changes,
            user_id=str(current_user.id),
        )
    
    db.commit()
    db.refresh(segment)
    return _segment_response(segment, db)


@router.delete("/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_segment(
    segment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_not_restricted),
):
    segment = db.query(Segment).filter(Segment.id == segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    
    # Audit: segment deleted
    audit_service.log_action_sync(
        db=db,
        action="segment.delete",
        entity_type="segment",
        entity_id=str(segment.id),
        old_values={
            "name": segment.name,
            "description": segment.description,
            "filters": segment.filters,
        },
        user_id=str(current_user.id),
    )
    
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

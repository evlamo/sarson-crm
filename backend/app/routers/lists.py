from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, insert, delete
from datetime import datetime
from app.utils.time import utcnow
import uuid

from app.database import get_db
from app.auth.dependencies import get_current_user, get_admin_user, require_not_restricted
from app.models.static_list import StaticList, StaticListMember
from app.models.contact import Contact
from app.models.segment import Segment
from app.models.user import User
from app.schemas.static_list import (
    StaticListCreate, StaticListUpdate, StaticListResponse,
    StaticListListResponse, ContactIdsRequest, StaticListContactsResponse,
)
from app.services.segment_service import build_segment_query
from app.services import audit_service

router = APIRouter(prefix="/api/v1/lists", tags=["static-lists"])


def _list_response(sl: StaticList, db: Session) -> StaticListResponse:
    count = db.query(func.count(StaticListMember.c.contact_id)).filter(
        StaticListMember.c.list_id == sl.id
    ).scalar()
    return StaticListResponse(
        id=sl.id,
        name=sl.name,
        description=sl.description,
        member_count=count,
        created_by=sl.created_by,
        created_at=sl.created_at,
        updated_at=sl.updated_at,
    )


def _get_list_or_404(list_id: uuid.UUID, db: Session) -> StaticList:
    sl = db.query(StaticList).filter(StaticList.id == list_id).first()
    if not sl:
        raise HTTPException(status_code=404, detail="Static list not found")
    return sl


@router.get("", response_model=StaticListListResponse)
def list_static_lists(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lists = db.query(StaticList).order_by(StaticList.name).all()
    data = [_list_response(sl, db) for sl in lists]
    return StaticListListResponse(data=data, total=len(data))


@router.get("/{list_id}", response_model=StaticListResponse)
def get_static_list(
    list_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _list_response(_get_list_or_404(list_id, db), db)


@router.post("", response_model=StaticListResponse, status_code=status.HTTP_201_CREATED)
def create_static_list(
    payload: StaticListCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sl = StaticList(
        name=payload.name,
        description=payload.description,
        created_by=current_user.id,
    )
    db.add(sl)
    db.commit()
    db.refresh(sl)
    
    audit_service.log_action_sync(
        db=db,
        action="list.create",
        entity_type="list",
        entity_id=str(sl.id),
        new_values={"name": sl.name, "description": sl.description},
        user_id=str(current_user.id),
    )
    db.commit()
    
    return _list_response(sl, db)


@router.put("/{list_id}", response_model=StaticListResponse)
def update_static_list(
    list_id: uuid.UUID,
    payload: StaticListUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sl = _get_list_or_404(list_id, db)
    old_values = {"name": sl.name, "description": sl.description}
    
    if payload.name is not None:
        sl.name = payload.name
    if payload.description is not None:
        sl.description = payload.description
    sl.updated_at = utcnow()
    
    new_values = {"name": sl.name, "description": sl.description}
    changes = {k: {"old": old_values[k], "new": new_values[k]} 
               for k in old_values if old_values[k] != new_values[k]}
    
    if changes:
        audit_service.log_action_sync(
            db=db,
            action="list.update",
            entity_type="list",
            entity_id=str(sl.id),
            old_values={k: v["old"] for k, v in changes.items()},
            new_values={k: v["new"] for k, v in changes.items()},
            user_id=str(current_user.id),
        )
    
    db.commit()
    db.refresh(sl)
    return _list_response(sl, db)


@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_static_list(
    list_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
    _: User = Depends(require_not_restricted),
):
    sl = _get_list_or_404(list_id, db)
    
    audit_service.log_action_sync(
        db=db,
        action="list.delete",
        entity_type="list",
        entity_id=str(sl.id),
        old_values={"name": sl.name, "description": sl.description},
        user_id=str(admin.id),
    )
    
    db.delete(sl)
    db.commit()


@router.get("/{list_id}/contacts", response_model=StaticListContactsResponse)
def get_list_contacts(
    list_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_list_or_404(list_id, db)

    total = db.query(func.count(StaticListMember.c.contact_id)).filter(
        StaticListMember.c.list_id == list_id
    ).scalar()

    contact_ids_q = (
        db.query(StaticListMember.c.contact_id)
        .filter(StaticListMember.c.list_id == list_id)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    contact_ids = [r[0] for r in contact_ids_q]

    contacts = (
        db.query(Contact)
        .options(joinedload(Contact.tags), joinedload(Contact.company_obj))
        .filter(Contact.id.in_(contact_ids), Contact.deleted_at.is_(None))
        .all()
    ) if contact_ids else []

    from app.routers.contacts import _build_response
    return StaticListContactsResponse(
        data=[_build_response(c).model_dump() for c in contacts],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("/{list_id}/contacts", status_code=status.HTTP_201_CREATED)
def add_contacts_to_list(
    list_id: uuid.UUID,
    payload: ContactIdsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sl = _get_list_or_404(list_id, db)

    existing = set(
        r[0] for r in db.query(StaticListMember.c.contact_id)
        .filter(StaticListMember.c.list_id == list_id)
        .all()
    )

    new_ids = [cid for cid in payload.contact_ids if cid not in existing]
    if new_ids:
        valid = set(
            r[0] for r in db.query(Contact.id)
            .filter(Contact.id.in_(new_ids), Contact.deleted_at.is_(None))
            .all()
        )
        rows = [{"list_id": list_id, "contact_id": cid} for cid in new_ids if cid in valid]
        if rows:
            db.execute(insert(StaticListMember), rows)
            
            audit_service.log_action_sync(
                db=db,
                action="list.add_contacts",
                entity_type="list",
                entity_id=str(list_id),
                new_values={"added_count": len(rows), "contact_ids": [str(r["contact_id"]) for r in rows[:10]]},
                user_id=str(current_user.id),
            )
            
            db.commit()

    return {"added": len(new_ids), "list_id": str(list_id)}


@router.delete("/{list_id}/contacts")
def remove_contacts_from_list(
    list_id: uuid.UUID,
    payload: ContactIdsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_not_restricted),
):
    _get_list_or_404(list_id, db)
    
    audit_service.log_action_sync(
        db=db,
        action="list.remove_contacts",
        entity_type="list",
        entity_id=str(list_id),
        old_values={"removed_count": len(payload.contact_ids), "contact_ids": [str(cid) for cid in payload.contact_ids[:10]]},
        user_id=str(current_user.id),
    )
    
    db.execute(
        delete(StaticListMember).where(
            StaticListMember.c.list_id == list_id,
            StaticListMember.c.contact_id.in_(payload.contact_ids),
        )
    )
    db.commit()
    return {"removed": len(payload.contact_ids), "list_id": str(list_id)}


@router.post("/{list_id}/from-segment/{segment_id}", response_model=StaticListResponse)
def snapshot_segment_to_list(
    list_id: uuid.UUID,
    segment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Snapshot a dynamic segment's current contacts into a static list."""
    sl = _get_list_or_404(list_id, db)
    segment = db.query(Segment).filter(Segment.id == segment_id).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    query = build_segment_query(db, segment.filters)
    contact_ids = [r[0] for r in query.with_entities(Contact.id).all()]

    existing = set(
        r[0] for r in db.query(StaticListMember.c.contact_id)
        .filter(StaticListMember.c.list_id == list_id)
        .all()
    )

    new_ids = [cid for cid in contact_ids if cid not in existing]
    if new_ids:
        db.execute(insert(StaticListMember), [{"list_id": list_id, "contact_id": cid} for cid in new_ids])
        
        audit_service.log_action_sync(
            db=db,
            action="list.snapshot_segment",
            entity_type="list",
            entity_id=str(list_id),
            new_values={"segment_id": str(segment_id), "segment_name": segment.name, "added_count": len(new_ids)},
            user_id=str(current_user.id),
        )
        
        db.commit()

    return _list_response(sl, db)

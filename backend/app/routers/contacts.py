from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, text, or_
from datetime import datetime, date
from typing import Optional, List
import uuid

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.contact import Contact
from app.models.company import Company
from app.models.tag import Tag
from app.models.activity import Activity
from app.schemas.contact import (
    ContactCreate,
    ContactUpdate,
    ContactPatch,
    ContactResponse,
    PaginatedContacts,
    BulkUpdateRequest,
    BulkUpdateResponse,
)
from app.models.user import User

router = APIRouter(prefix="/api/v1/contacts", tags=["contacts"])


# ── Helpers ────────────────────────────────────────────────────────────────

def _get_contact_or_404(contact_id: str, db: Session) -> Contact:
    contact = (
        db.query(Contact)
        .options(joinedload(Contact.tags), joinedload(Contact.company_obj))
        .filter(Contact.id == contact_id, Contact.deleted_at.is_(None))
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


def _build_response(contact: Contact) -> ContactResponse:
    """Enrich ContactResponse with computed fields."""
    data = ContactResponse.model_validate(contact)
    data.full_name = contact.full_name
    if contact.company_obj:
        data.company_name = contact.company_obj.name
    return data


# ── List / Search ──────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedContacts)
def list_contacts(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    search: Optional[str] = Query(None, max_length=300),
    status: Optional[str] = Query(None, max_length=50),
    contacted: Optional[bool] = Query(None),
    assigned_to: Optional[uuid.UUID] = Query(None),
    sarson_rep: Optional[str] = Query(None, max_length=255),
    sort: Optional[str] = Query("last_name", max_length=50),
    order: Optional[str] = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Paginated contact list with filters:
    - search: full-text via tsvector (falls back to ILIKE on name/email)
    - status, contacted, assigned_to, sarson_rep filters
    """
    query = (
        db.query(Contact)
        .options(joinedload(Contact.tags), joinedload(Contact.company_obj))
        .filter(Contact.deleted_at.is_(None))
    )

    # Full-text search
    if search:
        search_clean = search.strip()
        query = query.filter(
            or_(
                Contact.search_vector.op("@@")(func.plainto_tsquery("english", search_clean)),
                Contact.first_name.ilike(f"%{search_clean}%"),
                Contact.last_name.ilike(f"%{search_clean}%"),
                Contact.email.ilike(f"%{search_clean}%"),
                Contact.company.ilike(f"%{search_clean}%"),
            )
        )

    if status:
        query = query.filter(Contact.status == status)
    if contacted is not None:
        query = query.filter(Contact.contacted == contacted)
    if assigned_to:
        query = query.filter(Contact.assigned_to == assigned_to)
    if sarson_rep:
        query = query.filter(Contact.sarson_rep.ilike(f"%{sarson_rep}%"))

    # Whitelist of sortable fields → Contact column
    SORTABLE = {
        "last_name":        Contact.last_name,
        "first_name":       Contact.first_name,
        "company":          Contact.company,
        "title":            Contact.title,
        "email":            Contact.email,
        "phone":            Contact.phone,
        "status":           Contact.status,
        "contacted":        Contact.contacted,
        "last_contacted_at": Contact.last_contacted_at,
        "next_step":        Contact.next_step,
        "sarson_rep":       Contact.sarson_rep,
        "created_at":       Contact.created_at,
        "updated_at":       Contact.updated_at,
    }
    sort_col = SORTABLE.get(sort, Contact.last_name)
    sort_expr = sort_col.desc().nullslast() if order == "desc" else sort_col.asc().nullslast()

    # Always add tiebreaker secondary sorts for stable, predictable ordering
    if sort == "last_name":
        secondary = Contact.first_name.asc().nullslast()
    elif sort == "first_name":
        secondary = Contact.last_name.asc().nullslast()
    else:
        # For all other sorts, tiebreak by last_name then first_name
        secondary = Contact.last_name.asc().nullslast()

    total = query.count()
    contacts = (
        query.order_by(sort_expr, secondary)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return PaginatedContacts(
        data=[_build_response(c) for c in contacts],
        total=total,
        page=page,
        per_page=per_page,
    )


# ── Single Contact ─────────────────────────────────────────────────────────

@router.get("/{contact_id}", response_model=ContactResponse)
def get_contact(
    contact_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single contact with company and tags."""
    return _build_response(_get_contact_or_404(contact_id, db))


# ── Create ─────────────────────────────────────────────────────────────────

@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
def create_contact(
    payload: ContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a contact. email_domain is auto-extracted from email via model event."""
    data = payload.model_dump(exclude_unset=True)
    contact = Contact(**data)
    db.add(contact)
    db.commit()
    db.refresh(contact)
    # Reload with relationships
    return _build_response(_get_contact_or_404(str(contact.id), db))


# ── Full Update (PUT) ──────────────────────────────────────────────────────

@router.put("/{contact_id}", response_model=ContactResponse)
def update_contact(
    contact_id: str,
    payload: ContactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full update of a contact."""
    contact = _get_contact_or_404(contact_id, db)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)

    contact.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(contact)
    return _build_response(_get_contact_or_404(contact_id, db))


# ── Partial Update (PATCH) ─────────────────────────────────────────────────

@router.patch("/{contact_id}", response_model=ContactResponse)
def patch_contact(
    contact_id: str,
    payload: ContactPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Partial update — only provided fields are changed."""
    contact = _get_contact_or_404(contact_id, db)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)

    contact.updated_at = datetime.utcnow()
    db.commit()
    return _build_response(_get_contact_or_404(contact_id, db))


# ── Soft Delete ────────────────────────────────────────────────────────────

@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a contact (sets deleted_at, never hard deletes)."""
    contact = _get_contact_or_404(contact_id, db)
    contact.deleted_at = datetime.utcnow()
    db.commit()


# ── Activity Timeline ──────────────────────────────────────────────────────

@router.post("/{contact_id}/activities")
def create_contact_activity(
    contact_id: str,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a note/activity to a contact's timeline."""
    contact = _get_contact_or_404(contact_id, db)

    activity = Activity(
        contact_id=contact.id,
        activity_type=body.get("activity_type", "note"),
        subject=body.get("subject"),
        body=body.get("body"),
        performed_by=current_user.id,
        performed_at=datetime.utcnow(),
        source="manual",
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)

    return {
        "id": str(activity.id),
        "activity_type": activity.activity_type,
        "subject": activity.subject,
        "body": activity.body,
        "performed_at": activity.performed_at.isoformat(),
        "performed_by": str(activity.performed_by) if activity.performed_by else None,
        "source": activity.source,
    }


@router.get("/{contact_id}/activities")
def get_contact_activities(
    contact_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Contact activity timeline, newest first."""
    # Verify contact exists
    _get_contact_or_404(contact_id, db)

    query = db.query(Activity).filter(Activity.contact_id == contact_id)
    total = query.count()
    activities = (
        query.order_by(Activity.performed_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    # Return raw activity dicts (activity schema TBD in later raider)
    return {
        "data": [
            {
                "id": str(a.id),
                "activity_type": a.activity_type,
                "subject": a.subject,
                "body": a.body,
                "direction": a.direction,
                "outcome": a.outcome,
                "performed_at": a.performed_at.isoformat() if a.performed_at else None,
                "source": a.source,
            }
            for a in activities
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


# ── Bulk Update ────────────────────────────────────────────────────────────

@router.post("/bulk", response_model=BulkUpdateResponse)
def bulk_update_contacts(
    payload: BulkUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Bulk update contacts by ID list.
    Can set: status, assigned_to. Can add: tags (by ID list).
    """
    contacts = (
        db.query(Contact)
        .filter(
            Contact.id.in_(payload.ids),
            Contact.deleted_at.is_(None),
        )
        .all()
    )

    if not contacts:
        raise HTTPException(status_code=404, detail="No matching contacts found")

    # Scalar field updates
    update_fields = {}
    if payload.status is not None:
        update_fields["status"] = payload.status
    if payload.assigned_to is not None:
        update_fields["assigned_to"] = payload.assigned_to

    for contact in contacts:
        for field, value in update_fields.items():
            setattr(contact, field, value)
        contact.updated_at = datetime.utcnow()

    # Tag additions
    tags_added = 0
    if payload.tag_ids:
        tags = db.query(Tag).filter(Tag.id.in_(payload.tag_ids)).all()
        if not tags:
            raise HTTPException(status_code=404, detail="No matching tags found")
        for contact in contacts:
            for tag in tags:
                if tag not in contact.tags:
                    contact.tags.append(tag)
                    tags_added += 1

    db.commit()

    return BulkUpdateResponse(updated=len(contacts), tags_added=tags_added)

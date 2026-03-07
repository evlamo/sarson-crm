from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, text, or_, select
from sqlalchemy.exc import IntegrityError
from datetime import datetime, date, timezone
from typing import Optional, List
from pydantic import BaseModel, Field
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
from app.services.company_service import get_or_create_company

router = APIRouter(prefix="/api/v1/contacts", tags=["contacts"])

# ── Inline schemas ─────────────────────────────────────────────────────────

class ActivityCreate(BaseModel):
    activity_type: str = Field(default="note", max_length=50)
    subject: Optional[str] = Field(None, max_length=500)
    body: Optional[str] = Field(None, max_length=10000)

class BulkDeleteRequest(BaseModel):
    ids: List[uuid.UUID] = Field(..., min_length=1, max_length=500)

def _utcnow():
    return datetime.now(timezone.utc)


def _check_poc_enforcement(db: Session, contact_id, company_id, status_value: str):
    """Raise 409 if setting status to 'poc' but company already has a POC or no company assigned."""
    if status_value != "poc" and not company_id:
        return
    if not company_id:
        if status_value == "poc":
            raise HTTPException(
                status_code=409,
                detail="Cannot set POC status without assigning a company first.",
            )
        return
    if status_value != "poc":
        return
    existing_poc = (
        db.query(Contact)
        .filter(
            Contact.company_id == company_id,
            Contact.status == "poc",
            Contact.id != contact_id,
            Contact.deleted_at.is_(None),
        )
        .first()
    )
    if existing_poc:
        poc_name = existing_poc.full_name
        raise HTTPException(
            status_code=409,
            detail=f"This company already has a Point of Contact: {poc_name}. Remove their POC status first.",
        )


def _sync_poc_on_company(db: Session, contact):
    """If contact status is 'poc', set company.poc_contact_id."""
    if contact.status == "poc" and contact.company_id:
        company = db.query(Company).filter(Company.id == contact.company_id).first()
        if company:
            company.poc_contact_id = contact.id
    elif contact.company_id:
        # If status changed away from poc, clear if this contact was the poc
        company = db.query(Company).filter(Company.id == contact.company_id).first()
        if company and company.poc_contact_id == contact.id:
            company.poc_contact_id = None


def _resolve_company(db: Session, data: dict, contact=None):
    """Resolve company field to company_id via get_or_create_company."""
    company_name = data.get("company")
    if company_name is not None:
        co = get_or_create_company(db, company_name)
        if co:
            data["company_id"] = co.id
            data["company"] = co.name  # normalize casing
        else:
            data["company_id"] = None


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
    # Resolve company_name: prefer related Company object, fall back to text field
    if contact.company_obj:
        data.company_name = contact.company_obj.name
    elif contact.company:
        data.company_name = contact.company
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
    tag_id: Optional[str] = Query(None, max_length=36),
    sort: Optional[str] = Query("last_name", max_length=50),
    order: Optional[str] = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Paginated contact list with filters:
    - search: full-text via tsvector (falls back to ILIKE on name/email)
    - status, contacted, assigned_to, sarson_rep, tag_id filters
    """
    query = (
        db.query(Contact)
        .options(joinedload(Contact.tags), joinedload(Contact.company_obj))
        .filter(Contact.deleted_at.is_(None))
    )

    # Filter by tag
    if tag_id:
        query = query.filter(Contact.tags.any(Tag.id == tag_id))

    # Full-text search
    if search:
        search_clean = search.strip()
        # Escape ILIKE wildcards to prevent pattern injection
        search_escaped = search_clean.replace('\\', '\\\\').replace('%', r'\%').replace('_', r'\_')
        query = query.filter(
            or_(
                Contact.search_vector.op("@@")(func.plainto_tsquery("english", search_clean)),
                Contact.first_name.ilike(f"%{search_escaped}%"),
                Contact.last_name.ilike(f"%{search_escaped}%"),
                Contact.email.ilike(f"%{search_escaped}%"),
                Contact.company.ilike(f"%{search_escaped}%"),
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

    # Efficient count — no joins, just filter the base query
    total = db.query(func.count(Contact.id)).filter(
        Contact.deleted_at.is_(None),
        *([Contact.status == status] if status else []),
        *([Contact.contacted == contacted] if contacted is not None else []),
        *([Contact.assigned_to == assigned_to] if assigned_to else []),
        *([Contact.sarson_rep.ilike(f"%{sarson_rep}%")] if sarson_rep else []),
        *([Contact.tags.any(Tag.id == tag_id)] if tag_id else []),
        *([or_(
            Contact.search_vector.op("@@")(func.plainto_tsquery("english", search.strip())),
            Contact.first_name.ilike(f"%{search.strip().replace('%', r'%').replace('_', r'\_')}%"),
            Contact.last_name.ilike(f"%{search.strip().replace('%', r'%').replace('_', r'\_')}%"),
            Contact.email.ilike(f"%{search.strip().replace('%', r'%').replace('_', r'\_')}%"),
            Contact.company.ilike(f"%{search.strip().replace('%', r'%').replace('_', r'\_')}%"),
        )] if search else []),
    ).scalar()
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
    # Map schema field names → model column names
    if 'source' in data:
        data['lead_source'] = data.pop('source')
    # Auto-resolve company name → company_id
    _resolve_company(db, data)
    # Strip any keys that don't exist on the model to prevent TypeError
    valid_cols = {c.key for c in Contact.__table__.columns}
    data = {k: v for k, v in data.items() if k in valid_cols}
    # POC enforcement
    if data.get("status") == "poc" and data.get("company_id"):
        _check_poc_enforcement(db, None, data["company_id"], "poc")
    contact = Contact(**data)
    db.add(contact)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A contact with this email already exists")
    db.refresh(contact)
    _sync_poc_on_company(db, contact)
    db.commit()
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
    valid_cols = {c.key for c in Contact.__table__.columns}
    for field, value in payload.model_dump(exclude_unset=True).items():
        key = 'lead_source' if field == 'source' else field
        if key in valid_cols:
            setattr(contact, key, value)

    contact.updated_at = _utcnow()
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
    data = payload.model_dump(exclude_unset=True)
    # Map source → lead_source
    if 'source' in data:
        data['lead_source'] = data.pop('source')
    # Auto-resolve company name → company_id
    _resolve_company(db, data, contact)
    valid_cols = {c.key for c in Contact.__table__.columns}
    # Determine the final status and company_id for POC check
    new_status = data.get("status", contact.status)
    new_company_id = data.get("company_id", contact.company_id)
    if new_status == "poc":
        _check_poc_enforcement(db, contact.id, new_company_id, "poc")

    # Capture old status BEFORE applying changes for Google Ads trigger detection
    old_status = contact.status

    for key, value in data.items():
        if key in valid_cols:
            setattr(contact, key, value)

    # Auto-trigger Google Ads conversion only if status actually changed
    if "status" in data and data["status"] != old_status:
        from app.models.google_ads import GoogleAdsConversionAction
        from app.services.google_ads_service import is_gclid_valid
        trigger_action = db.query(GoogleAdsConversionAction).filter(
            GoogleAdsConversionAction.trigger_on_status == data["status"],
            GoogleAdsConversionAction.is_active == True,
        ).first()
        if trigger_action and contact.gclid and is_gclid_valid(contact.gclid_captured_at):
            contact.conversion_status = "pending"
            contact.conversion_name = trigger_action.name
            contact.conversion_value = contact.conversion_value or float(trigger_action.default_value or 0)

    contact.updated_at = _utcnow()
    _sync_poc_on_company(db, contact)
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
    contact.deleted_at = _utcnow()
    db.commit()


# ── Activity Timeline ──────────────────────────────────────────────────────

@router.post("/{contact_id}/activities")
def create_contact_activity(
    contact_id: str,
    body: ActivityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a note/activity to a contact's timeline."""
    contact = _get_contact_or_404(contact_id, db)

    activity = Activity(
        contact_id=contact.id,
        activity_type=body.activity_type,
        subject=body.subject,
        body=body.body,
        performed_by=current_user.id,
        performed_at=_utcnow(),
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


# ── Remove Tag from Contact ────────────────────────────────────────────────

@router.delete("/{contact_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_tag_from_contact(
    contact_id: str,
    tag_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a single tag from a contact."""
    contact = _get_contact_or_404(contact_id, db)
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    if tag in contact.tags:
        contact.tags.remove(tag)
        contact.updated_at = _utcnow()
        db.commit()


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
        contact.updated_at = _utcnow()

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


# ── Bulk Delete ────────────────────────────────────────────────────────────

@router.post("/bulk-delete", status_code=status.HTTP_200_OK)
def bulk_delete_contacts(
    payload: BulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete multiple contacts in a single DB round-trip."""
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

    now = _utcnow()
    for contact in contacts:
        contact.deleted_at = now

    db.commit()
    return {"deleted": len(contacts)}

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, text, or_, select
from sqlalchemy.exc import IntegrityError
from datetime import datetime, date, timezone
from typing import Optional, List
from pydantic import BaseModel, Field
import uuid

from app.database import get_db
from app.auth.dependencies import get_current_user, get_admin_user, require_not_restricted
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
from app.services.contact_service import get_contact_or_404 as _service_get_contact_or_404, build_contact_response as _service_build_response
from app.services import audit_service

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


def _escape_search(search: str) -> str:
    """Escape LIKE/ILIKE wildcards in search string."""
    s = search.strip()
    s = s.replace("%", "\%")
    s = s.replace("_", "\_")
    return s


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
            data["company"] = co.name
        else:
            data["company_id"] = None


# ── Helpers ────────────────────────────────────────────────────────────────

def _get_contact_or_404(contact_id: str, db: Session) -> Contact:
    """Local shim — delegates to contact_service.get_contact_or_404."""
    return _service_get_contact_or_404(db, contact_id)


def _build_response(contact: Contact) -> ContactResponse:
    """Local shim — delegates to contact_service.build_contact_response."""
    return _service_build_response(contact)


def _capture_contact_snapshot(contact: Contact, fields: Optional[List[str]] = None) -> dict:
    """Capture current values of a contact for audit comparison."""
    snapshot = {}
    target_fields = fields or [
        "first_name", "last_name", "email", "phone", "title", "company",
        "company_id", "status", "sarson_rep", "city", "state", "country",
        "linkedin_url", "website", "notes", "next_step", "lead_source",
        "contact_method_preference", "contact_method_custom", "last_contacted_at",
    ]
    for field in target_fields:
        val = getattr(contact, field, None)
        if val is not None:
            snapshot[field] = str(val) if not isinstance(val, str) else val
        else:
            snapshot[field] = None
    return snapshot


def _compute_changes(old_snapshot: dict, new_snapshot: dict) -> dict:
    """Compare two snapshots and return dict of changes."""
    changes = {}
    all_keys = set(old_snapshot.keys()) | set(new_snapshot.keys())
    for key in all_keys:
        old_val = old_snapshot.get(key)
        new_val = new_snapshot.get(key)
        if old_val != new_val:
            changes[key] = {"old": old_val, "new": new_val}
    return changes


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
    _: User = Depends(require_not_restricted),
):
    query = (
        db.query(Contact)
        .options(joinedload(Contact.tags), joinedload(Contact.company_obj))
        .filter(Contact.deleted_at.is_(None))
    )

    if tag_id:
        query = query.filter(Contact.tags.any(Tag.id == tag_id))

    if search:
        search_clean = search.strip()
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

    if sort == "last_name":
        secondary = Contact.first_name.asc().nullslast()
    elif sort == "first_name":
        secondary = Contact.last_name.asc().nullslast()
    else:
        secondary = Contact.last_name.asc().nullslast()

    total = db.query(func.count(Contact.id)).filter(
        Contact.deleted_at.is_(None),
        *([Contact.status == status] if status else []),
        *([Contact.contacted == contacted] if contacted is not None else []),
        *([Contact.assigned_to == assigned_to] if assigned_to else []),
        *([Contact.sarson_rep.ilike(f"%{sarson_rep}%")] if sarson_rep else []),
        *([Contact.tags.any(Tag.id == tag_id)] if tag_id else []),
        *([or_(
            Contact.search_vector.op("@@")(func.plainto_tsquery("english", search.strip())),
            Contact.first_name.ilike(f"%{_escape_search(search)}%"),
            Contact.last_name.ilike(f"%{_escape_search(search)}%"),
            Contact.email.ilike(f"%{_escape_search(search)}%"),
            Contact.company.ilike(f"%{_escape_search(search)}%"),
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
    _: User = Depends(require_not_restricted),
):
    return _build_response(_get_contact_or_404(contact_id, db))


# ── Create ─────────────────────────────────────────────────────────────────

@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
def create_contact(
    payload: ContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_not_restricted),
):
    data = payload.model_dump(exclude_unset=True)
    if 'source' in data:
        data['lead_source'] = data.pop('source')
    _resolve_company(db, data)
    valid_cols = {c.key for c in Contact.__table__.columns}
    data = {k: v for k, v in data.items() if k in valid_cols}
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
    
    # Audit log: contact created
    audit_service.log_action_sync(
        db=db,
        action="contact.create",
        entity_type="contact",
        entity_id=str(contact.id),
        new_values=_capture_contact_snapshot(contact),
        user_id=str(current_user.id),
    )
    db.commit()
    return _build_response(_get_contact_or_404(str(contact.id), db))


# ── Full Update (PUT) ──────────────────────────────────────────────────────

@router.put("/{contact_id}", response_model=ContactResponse)
def update_contact(
    contact_id: str,
    payload: ContactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_not_restricted),
):
    contact = _get_contact_or_404(contact_id, db)
    old_snapshot = _capture_contact_snapshot(contact)
    valid_cols = {c.key for c in Contact.__table__.columns}
    for field, value in payload.model_dump(exclude_unset=True).items():
        key = 'lead_source' if field == 'source' else field
        if key in valid_cols:
            setattr(contact, key, value)

    contact.updated_at = _utcnow()
    
    new_snapshot = _capture_contact_snapshot(contact)
    changes = _compute_changes(old_snapshot, new_snapshot)
    
    if changes:
        audit_service.log_entity_changes_sync(
            db=db,
            entity=contact,
            changes=changes,
            action="contact.update",
            entity_type="contact",
            user_id=str(current_user.id),
        )
    
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
    _: User = Depends(require_not_restricted),
):
    contact = _get_contact_or_404(contact_id, db)
    old_snapshot = _capture_contact_snapshot(contact)
    
    data = payload.model_dump(exclude_unset=True)
    if 'source' in data:
        data['lead_source'] = data.pop('source')
    _resolve_company(db, data, contact)
    valid_cols = {c.key for c in Contact.__table__.columns}
    new_status = data.get("status", contact.status)
    new_company_id = data.get("company_id", contact.company_id)
    if new_status == "poc":
        _check_poc_enforcement(db, contact.id, new_company_id, "poc")

    old_status = contact.status

    for key, value in data.items():
        if key in valid_cols:
            setattr(contact, key, value)

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

    # Auto-set master_dnc when email_unsubscribed becomes True
    if data.get("email_unsubscribed") is True and not contact.master_dnc:
        contact.master_dnc = True
        contact.master_dnc_reason = "Email unsubscribe"
        contact.master_dnc_set_at = _utcnow()

    contact.updated_at = _utcnow()
    _sync_poc_on_company(db, contact)
    
    new_snapshot = _capture_contact_snapshot(contact)
    changes = _compute_changes(old_snapshot, new_snapshot)
    
    if changes:
        audit_service.log_entity_changes_sync(
            db=db,
            entity=contact,
            changes=changes,
            action="contact.update",
            entity_type="contact",
            user_id=str(current_user.id),
        )
    
    db.commit()
    return _build_response(_get_contact_or_404(contact_id, db))


# ── Soft Delete ────────────────────────────────────────────────────────────

@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_not_restricted),
):
    contact = _get_contact_or_404(contact_id, db)
    old_snapshot = _capture_contact_snapshot(contact)
    contact.deleted_at = _utcnow()
    
    audit_service.log_action_sync(
        db=db,
        action="contact.delete",
        entity_type="contact",
        entity_id=str(contact.id),
        old_values=old_snapshot,
        user_id=str(current_user.id),
    )
    db.commit()


# ── Activity Timeline ──────────────────────────────────────────────────────

@router.post("/{contact_id}/activities")
def create_contact_activity(
    contact_id: str,
    body: ActivityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_not_restricted),
):
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
    _: User = Depends(require_not_restricted),
):
    _get_contact_or_404(contact_id, db)

    query = db.query(Activity).filter(Activity.contact_id == contact_id)
    total = query.count()
    activities = (
        query.order_by(Activity.performed_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

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
    _: User = Depends(require_not_restricted),
):
    contact = _get_contact_or_404(contact_id, db)
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    if tag in contact.tags:
        contact.tags.remove(tag)
        contact.updated_at = _utcnow()
        
        audit_service.log_action_sync(
            db=db,
            action="contact.remove_tag",
            entity_type="contact",
            entity_id=str(contact.id),
            old_values={"tag_id": str(tag.id), "tag_name": tag.name},
            user_id=str(current_user.id),
        )
        db.commit()


# ── Add Tag by ID ──────────────────────────────────────────────────────────

@router.post("/{contact_id}/tags/by-id")
def add_tag_to_contact_by_id(
    contact_id: str,
    tag_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_not_restricted),
):
    contact = _get_contact_or_404(contact_id, db)
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    if tag not in contact.tags:
        contact.tags.append(tag)
        contact.updated_at = _utcnow()
        
        audit_service.log_action_sync(
            db=db,
            action="contact.add_tag",
            entity_type="contact",
            entity_id=str(contact.id),
            new_values={"tag_id": str(tag.id), "tag_name": tag.name},
            user_id=str(current_user.id),
        )
        db.commit()
    return {"status": "ok", "tag_id": str(tag.id)}


# ── Add Tag by Name (create if needed) ─────────────────────────────────────

class TagNameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)

@router.post("/{contact_id}/tags")
def add_tag_to_contact_by_name(
    contact_id: str,
    payload: TagNameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_not_restricted),
):
    contact = _get_contact_or_404(contact_id, db)
    tag_name = payload.name.strip()
    tag = db.query(Tag).filter(func.lower(Tag.name) == func.lower(tag_name)).first()
    if not tag:
        tag = Tag(name=tag_name)
        db.add(tag)
        db.flush()
    if tag not in contact.tags:
        contact.tags.append(tag)
        contact.updated_at = _utcnow()
        
        audit_service.log_action_sync(
            db=db,
            action="contact.add_tag",
            entity_type="contact",
            entity_id=str(contact.id),
            new_values={"tag_id": str(tag.id), "tag_name": tag.name},
            user_id=str(current_user.id),
        )
    db.commit()
    return {"status": "ok", "tag": {"id": str(tag.id), "name": tag.name}}


# ── Bulk Update ────────────────────────────────────────────────────────────

@router.post("/bulk", response_model=BulkUpdateResponse)
def bulk_update_contacts(
    payload: BulkUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_not_restricted),
):
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

    update_fields = {}
    if payload.status is not None:
        update_fields["status"] = payload.status
    if payload.assigned_to is not None:
        update_fields["assigned_to"] = payload.assigned_to

    for contact in contacts:
        for field, value in update_fields.items():
            setattr(contact, field, value)
        contact.updated_at = _utcnow()

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

    # Audit log: bulk update
    audit_service.log_action_sync(
        db=db,
        action="contact.bulk_update",
        entity_type="contact",
        entity_id=None,
        new_values={
            "contact_count": len(contacts),
            "contact_ids": [str(c.id) for c in contacts[:10]],
            "updates": update_fields,
            "tags_added": tags_added,
        },
        user_id=str(current_user.id),
    )
    
    db.commit()

    return BulkUpdateResponse(updated=len(contacts), tags_added=tags_added)


# ── Bulk Delete ────────────────────────────────────────────────────────────

@router.post("/bulk-delete", status_code=status.HTTP_200_OK)
def bulk_delete_contacts(
    payload: BulkDeleteRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
    _: User = Depends(require_not_restricted),
):
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
    contact_ids = [str(c.id) for c in contacts]
    for contact in contacts:
        contact.deleted_at = now

    audit_service.log_action_sync(
        db=db,
        action="contact.bulk_delete",
        entity_type="contact",
        entity_id=None,
        old_values={
            "contact_count": len(contacts),
            "contact_ids": contact_ids[:20],
        },
        user_id=str(admin.id),
    )
    
    db.commit()
    return {"deleted": len(contacts)}


# ──────────────────────────────────────────────────────────────────────────────
# CAMPAIGN EXCLUSION LOGIC - Contact DNC & Campaign Membership Endpoints
# ──────────────────────────────────────────────────────────────────────────────

from app.models.sales_campaign import SalesCampaign, CampaignContact


# ── Schemas for Campaign Membership ────────────────────────────────────────────

class ContactCampaignMembership(BaseModel):
    campaign_id: uuid.UUID
    campaign_name: str
    status: str
    added_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContactCampaignsResponse(BaseModel):
    data: List[ContactCampaignMembership]
    total: int


class CampaignStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(active|completed|no|excluded|paused)$")


class SetDNCRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)


# ── Get Contact Campaign Memberships ───────────────────────────────────────────

@router.get("/{contact_id}/campaigns", response_model=ContactCampaignsResponse)
def get_contact_campaigns(
    contact_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all sales campaigns this contact belongs to with their status."""
    contact = _get_contact_or_404(contact_id, db)
    
    # Join CampaignContact with SalesCampaign to get campaign details
    memberships = (
        db.query(CampaignContact, SalesCampaign)
        .join(SalesCampaign, CampaignContact.sales_campaign_id == SalesCampaign.id)
        .filter(
            CampaignContact.contact_id == contact.id,
            SalesCampaign.status != "archived",
        )
        .order_by(CampaignContact.added_at.desc())
        .all()
    )
    
    data = [
        ContactCampaignMembership(
            campaign_id=campaign.id,
            campaign_name=campaign.name,
            status=cc.status or "active",
            added_at=cc.added_at,
            updated_at=cc.updated_at,
        )
        for cc, campaign in memberships
    ]
    
    return ContactCampaignsResponse(data=data, total=len(data))


# ── Update Contact Status in Campaign ──────────────────────────────────────────

@router.put("/{contact_id}/campaigns/{campaign_id}")
def update_contact_campaign_status(
    contact_id: str,
    campaign_id: uuid.UUID,
    data: CampaignStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a contact's status in a specific sales campaign."""
    contact = _get_contact_or_404(contact_id, db)
    
    # Find the campaign contact record
    cc = db.query(CampaignContact).filter(
        CampaignContact.contact_id == contact.id,
        CampaignContact.sales_campaign_id == campaign_id,
    ).first()
    
    if not cc:
        raise HTTPException(status_code=404, detail="Contact is not in this campaign")
    
    old_status = cc.status
    cc.status = data.status
    cc.updated_at = _utcnow()
    
    # Set completion_status if status is completed or no
    if data.status in ("completed", "no"):
        cc.completion_status = data.status
        cc.excluded_reason = "campaign_complete"
    elif data.status == "active":
        # Reset completion status when reactivating
        cc.completion_status = None
        if cc.excluded_reason == "campaign_complete":
            cc.excluded_reason = None
    
    audit_service.log_action_sync(
        db=db,
        action="campaign_contact.status_update",
        entity_type="campaign_contact",
        entity_id=str(contact.id),
        old_values={"status": old_status, "campaign_id": str(campaign_id)},
        new_values={"status": data.status, "campaign_id": str(campaign_id)},
        user_id=str(current_user.id),
    )
    
    db.commit()
    
    return {
        "contact_id": str(contact.id),
        "campaign_id": str(campaign_id),
        "status": cc.status,
        "updated_at": cc.updated_at.isoformat(),
    }


# ── Set Contact DNC ────────────────────────────────────────────────────────────

@router.post("/{contact_id}/dnc")
def set_contact_dnc(
    contact_id: str,
    data: SetDNCRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """Set master DNC status on a contact. Admin only."""
    contact = _get_contact_or_404(contact_id, db)
    
    if contact.master_dnc:
        raise HTTPException(status_code=409, detail="Contact already has DNC status")
    
    contact.master_dnc = True
    contact.master_dnc_reason = data.reason or "Manual DNC"
    contact.master_dnc_set_at = _utcnow()
    contact.master_dnc_set_by = current_user.id
    contact.updated_at = _utcnow()
    
    # Exclude from all active campaign memberships
    db.query(CampaignContact).filter(
        CampaignContact.contact_id == contact.id,
        CampaignContact.excluded_reason.is_(None),
    ).update({
        CampaignContact.excluded_reason: "dnc",
        CampaignContact.status: "excluded",
    }, synchronize_session=False)
    
    audit_service.log_action_sync(
        db=db,
        action="contact.dnc_set",
        entity_type="contact",
        entity_id=str(contact.id),
        old_values={"master_dnc": False},
        new_values={"master_dnc": True, "master_dnc_reason": contact.master_dnc_reason},
        user_id=str(current_user.id),
    )
    
    db.commit()
    
    return {
        "contact_id": str(contact.id),
        "master_dnc": True,
        "master_dnc_reason": contact.master_dnc_reason,
        "master_dnc_set_at": contact.master_dnc_set_at.isoformat(),
    }


# ── Clear Contact DNC ──────────────────────────────────────────────────────────

@router.delete("/{contact_id}/dnc", status_code=status.HTTP_204_NO_CONTENT)
def clear_contact_dnc(
    contact_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
    _: User = Depends(require_not_restricted),
):
    """Clear master DNC status from a contact. Admin only."""
    contact = _get_contact_or_404(contact_id, db)
    
    if not contact.master_dnc:
        raise HTTPException(status_code=400, detail="Contact is not on the DNC list")
    
    old_reason = contact.master_dnc_reason
    
    contact.master_dnc = False
    contact.master_dnc_reason = None
    contact.master_dnc_set_at = None
    contact.master_dnc_set_by = None
    contact.updated_at = _utcnow()
    
    # Restore campaign access - clear DNC exclusions (set back to active)
    db.query(CampaignContact).filter(
        CampaignContact.contact_id == contact.id,
        CampaignContact.excluded_reason == "dnc",
    ).update({
        CampaignContact.excluded_reason: None,
        CampaignContact.status: "active",
    }, synchronize_session=False)
    
    audit_service.log_action_sync(
        db=db,
        action="contact.dnc_cleared",
        entity_type="contact",
        entity_id=str(contact.id),
        old_values={"master_dnc": True, "master_dnc_reason": old_reason},
        new_values={"master_dnc": False},
        user_id=str(current_user.id),
    )
    
    db.commit()

"""
Google Ads OCT router — /api/v1/google-ads
"""
import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, cast, Date

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.auth.dependencies import get_current_user, get_admin_user, require_not_restricted
from app.models.user import User
from app.models.contact import Contact
from app.models.google_ads import ConversionSyncHistory, GoogleAdsConversionAction
from app.schemas.google_ads import (
    ConversionActionCreate, ConversionActionUpdate, ConversionActionOut,
    ManualConversionRequest, ConversionSyncHistoryOut, ContactGCLIDCapture,
    GoogleAdsStatsOut,
)
from app.config import settings
from app.services import google_ads_service

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/api/v1/google-ads", tags=["google-ads"])


def _utcnow():
    return datetime.now(timezone.utc)


# ── Stats ──────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=GoogleAdsStatsOut)
def get_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    now = _utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    synced_today = db.query(func.count(ConversionSyncHistory.id)).filter(
        ConversionSyncHistory.sync_status == "success",
        ConversionSyncHistory.synced_at >= today_start,
    ).scalar() or 0

    pending = db.query(func.count(ConversionSyncHistory.id)).filter(
        ConversionSyncHistory.sync_status.in_(["pending", "transient_error"]),
    ).scalar() or 0

    errors = db.query(func.count(ConversionSyncHistory.id)).filter(
        ConversionSyncHistory.sync_status == "permanent_error",
    ).scalar() or 0

    total = db.query(func.count(ConversionSyncHistory.id)).filter(
        ConversionSyncHistory.sync_status == "success",
    ).scalar() or 0

    return GoogleAdsStatsOut(synced_today=synced_today, pending=pending, errors=errors, total_all_time=total)


# ── Conversion Actions (admin) ─────────────────────────────────────────────

@router.get("/conversion-actions", response_model=list[ConversionActionOut])
def list_conversion_actions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    actions = db.query(GoogleAdsConversionAction).order_by(GoogleAdsConversionAction.created_at.desc()).all()
    return [ConversionActionOut(
        id=str(a.id), name=a.name, google_conversion_action_id=a.google_conversion_action_id,
        default_value=float(a.default_value or 0), trigger_on_status=a.trigger_on_status,
        is_active=a.is_active, created_at=a.created_at,
    ) for a in actions]


@router.post("/conversion-actions", response_model=ConversionActionOut, status_code=201)
def create_conversion_action(
    body: ConversionActionCreate, db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    action = GoogleAdsConversionAction(
        name=body.name, google_conversion_action_id=body.google_conversion_action_id,
        default_value=body.default_value, trigger_on_status=body.trigger_on_status,
        is_active=body.is_active,
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return ConversionActionOut(
        id=str(action.id), name=action.name, google_conversion_action_id=action.google_conversion_action_id,
        default_value=float(action.default_value or 0), trigger_on_status=action.trigger_on_status,
        is_active=action.is_active, created_at=action.created_at,
    )


@router.patch("/conversion-actions/{action_id}", response_model=ConversionActionOut)
def update_conversion_action(
    action_id: str, body: ConversionActionUpdate, db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    action = db.query(GoogleAdsConversionAction).filter(GoogleAdsConversionAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Conversion action not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(action, key, value)
    db.commit()
    db.refresh(action)
    return ConversionActionOut(
        id=str(action.id), name=action.name, google_conversion_action_id=action.google_conversion_action_id,
        default_value=float(action.default_value or 0), trigger_on_status=action.trigger_on_status,
        is_active=action.is_active, created_at=action.created_at,
    )


@router.delete("/conversion-actions/{action_id}", status_code=204)
def delete_conversion_action(
    action_id: str, db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
    _: User = Depends(require_not_restricted),
):
    action = db.query(GoogleAdsConversionAction).filter(GoogleAdsConversionAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Conversion action not found")
    db.delete(action)
    db.commit()


# ── Conversion Log ─────────────────────────────────────────────────────────

@router.get("/conversions")
def list_conversions(
    status: Optional[str] = None, page: int = Query(1, ge=1), per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    q = db.query(ConversionSyncHistory)
    if status:
        q = q.filter(ConversionSyncHistory.sync_status == status)
    total = q.count()
    records = q.order_by(ConversionSyncHistory.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    # Fetch contact names
    contact_ids = [r.contact_id for r in records if r.contact_id]
    contacts_map = {}
    if contact_ids:
        contacts = db.query(Contact.id, Contact.first_name, Contact.last_name, Contact.email).filter(Contact.id.in_(contact_ids)).all()
        contacts_map = {str(c.id): {"name": f"{c.first_name or ''} {c.last_name or ''}".strip(), "email": c.email} for c in contacts}

    data = []
    for r in records:
        contact_info = contacts_map.get(str(r.contact_id), {})
        data.append({
            "id": str(r.id), "contact_id": str(r.contact_id) if r.contact_id else None,
            "contact_name": contact_info.get("name", ""), "contact_email": contact_info.get("email", ""),
            "gclid": r.gclid, "conversion_name": r.conversion_name,
            "conversion_value": float(r.conversion_value) if r.conversion_value else None,
            "conversion_time": r.conversion_time.isoformat() if r.conversion_time else None,
            "sync_status": r.sync_status, "error_message": r.error_message,
            "error_code": r.error_code, "retry_count": r.retry_count,
            "synced_at": r.synced_at.isoformat() if r.synced_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return {"data": data, "total": total, "page": page, "per_page": per_page}


# ── Contacts with GCLID ───────────────────────────────────────────────────

@router.get("/contacts")
def list_gclid_contacts(
    page: int = Query(1, ge=1), per_page: int = Query(25, ge=1, le=100),
    expired: bool = False,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    now = _utcnow()
    q = db.query(Contact).filter(Contact.gclid.isnot(None), Contact.deleted_at.is_(None))
    if not expired:
        q = q.filter(Contact.gclid_expires_at > now)
    total = q.count()
    contacts = q.order_by(Contact.gclid_captured_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    data = []
    for c in contacts:
        data.append({
            "id": str(c.id),
            "name": f"{c.first_name or ''} {c.last_name or ''}".strip() or c.email or "Unknown",
            "email": c.email, "status": c.status,
            "gclid": f"...{c.gclid[-8:]}" if c.gclid and len(c.gclid) > 8 else c.gclid,
            "gclid_captured_at": c.gclid_captured_at.isoformat() if c.gclid_captured_at else None,
            "gclid_expires_at": c.gclid_expires_at.isoformat() if c.gclid_expires_at else None,
            "conversion_status": c.conversion_status,
            "conversion_synced_at": c.conversion_synced_at.isoformat() if c.conversion_synced_at else None,
        })
    return {"data": data, "total": total, "page": page, "per_page": per_page}


# ── Manual Conversion Trigger ─────────────────────────────────────────────

@router.post("/contacts/{contact_id}/convert")
async def manual_convert(
    contact_id: str, body: ManualConversionRequest,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    contact = db.query(Contact).filter(Contact.id == contact_id, Contact.deleted_at.is_(None)).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    if not contact.gclid:
        raise HTTPException(status_code=400, detail="Contact has no GCLID")
    if not google_ads_service.is_gclid_valid(contact.gclid_captured_at):
        raise HTTPException(status_code=400, detail="GCLID has expired (>90 days)")

    # Look up conversion action
    action = db.query(GoogleAdsConversionAction).filter(
        GoogleAdsConversionAction.name == body.conversion_name,
        GoogleAdsConversionAction.is_active == True,
    ).first()
    if not action:
        raise HTTPException(status_code=404, detail=f"Conversion action '{body.conversion_name}' not found or inactive")
    if not action.google_conversion_action_id:
        raise HTTPException(status_code=400, detail="Conversion action has no Google Ads Action ID configured")

    now = _utcnow()
    value = body.conversion_value if body.conversion_value is not None else float(action.default_value or 0)

    result = await google_ads_service.upload_click_conversion(
        gclid=contact.gclid,
        conversion_action_id=action.google_conversion_action_id,
        conversion_time=now,
        conversion_value=value,
        email=contact.email,
    )

    history = ConversionSyncHistory(
        contact_id=contact.id, gclid=contact.gclid, conversion_name=action.name,
        conversion_value=value, conversion_time=now,
        hashed_email=google_ads_service.hash_email(contact.email) if contact.email else None,
        sync_status=result["status"], error_message=result.get("error"),
        error_code=result.get("error_code"), google_response=result.get("response"),
        synced_at=now if result["status"] == "success" else None,
    )
    db.add(history)

    contact.conversion_status = "synced" if result["status"] == "success" else result["status"]
    contact.conversion_synced = result["status"] == "success"
    contact.conversion_synced_at = now if result["status"] == "success" else None
    contact.conversion_name = action.name
    contact.conversion_value = value
    db.commit()

    return {"status": result["status"], "error": result.get("error"), "history_id": str(history.id)}


# ── GCLID Capture (unauthenticated) ───────────────────────────────────────

@router.post("/capture")
@limiter.limit("30/minute")
def capture_gclid(request: Request, body: ContactGCLIDCapture, db: Session = Depends(get_db)):
    # Validate GCLID format — base64url chars only, 20-250 length
    if not re.match(r'^[A-Za-z0-9_\-]{20,250}$', body.gclid):
        raise HTTPException(status_code=400, detail="Invalid GCLID format")

    contact = None
    if body.contact_id:
        contact = db.query(Contact).filter(Contact.id == body.contact_id, Contact.deleted_at.is_(None)).first()
    elif body.email:
        contact = db.query(Contact).filter(Contact.email == body.email, Contact.deleted_at.is_(None)).first()

    if not contact:
        # Don't reveal whether contact exists — return generic success
        # TODO: Zoho parity gap — optionally auto-create contact here for Google Ads leads
        return {"received": True}

    now = _utcnow()
    contact.gclid = body.gclid
    contact.gclid_captured_at = now
    contact.gclid_expires_at = now + timedelta(days=90)
    db.commit()
    return {"received": True}


# ── JS Snippet (admin) ────────────────────────────────────────────────────

@router.get("/snippet")
def get_snippet(
    hidden_field_id: str = "gclid_field", cookie_name: str = "_sarson_gclid",
    current_user: User = Depends(get_admin_user),
):
    snippet = google_ads_service.generate_tracking_snippet({
        "hidden_field_id": hidden_field_id, "cookie_name": cookie_name,
    })
    return {"snippet": snippet}


# ── Auth Status / Test (admin) ─────────────────────────────────────────────

@router.get("/auth/status")
def auth_status(current_user: User = Depends(get_admin_user)):
    from app.config import settings
    has_client_id = bool(settings.google_ads_client_id)
    has_client_secret = bool(settings.google_ads_client_secret)
    has_refresh_token = bool(settings.google_ads_refresh_token)
    has_developer_token = bool(settings.google_ads_developer_token)
    has_customer_id = bool(settings.google_ads_customer_id)

    configured = all([has_client_id, has_client_secret, has_refresh_token, has_developer_token, has_customer_id])
    return {
        "configured": configured,
        "client_id": f"...{settings.google_ads_client_id[-8:]}" if has_client_id else None,
        "customer_id": settings.google_ads_customer_id if has_customer_id else None,
        "has_refresh_token": has_refresh_token,
        "has_developer_token": has_developer_token,
    }


@router.post("/auth/test")
async def test_auth(current_user: User = Depends(get_admin_user)):
    try:
        token = await google_ads_service.get_access_token()
        # Quick test: try a lightweight API call to verify scope/permissions
        import httpx
        cid = settings.google_ads_customer_id.replace("-", "") if settings.google_ads_customer_id else ""
        url = f"{google_ads_service.GOOGLE_ADS_BASE_URL}/{google_ads_service.GOOGLE_ADS_API_VERSION}/customers/{cid}"
        headers = google_ads_service._get_headers(token)
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url, headers=headers)
        if r.status_code == 403:
            return {"status": "error", "message": "Auth works but permission denied. Verify the OAuth2 scope 'https://www.googleapis.com/auth/adwords' was granted and the customer ID is correct."}
        return {"status": "connected", "message": "Successfully obtained access token"}
    except HTTPException as e:
        return {"status": "error", "message": e.detail}
    except Exception as e:
        return {"status": "error", "message": str(e)}

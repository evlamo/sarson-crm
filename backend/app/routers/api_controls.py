"""
API Controls router — admin-only management of external API credentials.
"""
import logging
from datetime import datetime, timezone

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.api_credentials import ApiCredentials
from app.models.user import User
from app.schemas.api_credentials import (
    ApiCredentialsResponse, ApiCredentialsTestResponse, MailchimpCredentialsUpdate
)
from app.services import api_credentials_service
from app.services.api_credentials_service import PROVIDER_FIELDS, get_masked_fields

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/api-controls", tags=["api-controls"])


def _require_admin(user: User):
    """Check if user has admin or owner role."""
    if getattr(user, 'role', None) not in ('admin', 'owner'):
        raise HTTPException(status_code=403, detail="Admin access required")


def _build_response(creds: ApiCredentials, provider: str) -> ApiCredentialsResponse:
    return ApiCredentialsResponse(
        id=creds.id,
        provider=creds.provider,
        is_configured=creds.is_configured,
        last_tested_at=creds.last_tested_at,
        last_test_status=creds.last_test_status,
        last_test_message=creds.last_test_message,
        updated_at=creds.updated_at,
        masked_fields=get_masked_fields(creds, provider),
    )


@router.get("/providers")
def list_providers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    providers = []
    for provider, fields in PROVIDER_FIELDS.items():
        creds = api_credentials_service.get_credentials(db, provider)
        providers.append({
            "provider": provider,
            "label": provider.replace("_", " ").title(),
            "is_configured": creds.is_configured if creds else False,
            "last_tested_at": creds.last_tested_at if creds else None,
            "last_test_status": creds.last_test_status if creds else None,
            "fields": [
                {
                    "key": k,
                    "label": v["label"],
                    "sensitive": v["sensitive"],
                    "placeholder": v["placeholder"],
                    "help": v["help"],
                    "current_value": get_masked_fields(creds, provider).get(k, "") if creds else "",
                }
                for k, v in fields.items()
            ],
        })
    return providers


@router.get("/{provider}")
def get_provider(
    provider: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    if provider not in PROVIDER_FIELDS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")
    creds = api_credentials_service.get_credentials(db, provider)
    if not creds:
        return {
            "provider": provider,
            "is_configured": False,
            "masked_fields": {},
            "fields": PROVIDER_FIELDS[provider],
        }
    return _build_response(creds, provider)


@router.put("/mailchimp")
def update_mailchimp(
    data: MailchimpCredentialsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    creds = api_credentials_service.update_credentials(db, "mailchimp", {
        "api_key": data.api_key,
        "server_prefix": data.server_prefix,
        "audience_id": data.audience_id,
        "from_email": data.from_email,
        "from_name": data.from_name,
        "webhook_secret": data.webhook_secret,
    })
    return _build_response(creds, "mailchimp")


@router.put("/{provider}")
def update_provider(
    provider: str,
    data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    if provider not in PROVIDER_FIELDS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")
    allowed_fields = set(PROVIDER_FIELDS[provider].keys())
    filtered = {k: v for k, v in data.items() if k in allowed_fields}
    # Validate all values are strings or None
    for k, v in filtered.items():
        if v is not None and not isinstance(v, str):
            raise HTTPException(status_code=422, detail=f"Field '{k}' must be a string")
    creds = api_credentials_service.update_credentials(db, provider, filtered)
    return _build_response(creds, provider)


@router.post("/mailchimp/test")
async def test_mailchimp(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    from app.services.mailchimp_service import test_mailchimp_connection
    result = await test_mailchimp_connection(db=db)

    creds = api_credentials_service.get_credentials(db, "mailchimp")
    if creds:
        creds.last_tested_at = datetime.now(timezone.utc)
        creds.last_test_status = "success" if result["success"] else "failed"
        creds.last_test_message = result["message"]
        creds.updated_at = datetime.now(timezone.utc)
        db.commit()

    return ApiCredentialsTestResponse(
        provider="mailchimp",
        success=result["success"],
        message=result["message"],
        detail=result.get("detail"),
    )


@router.post("/{provider}/test")
async def test_provider(
    provider: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    return ApiCredentialsTestResponse(
        provider=provider,
        success=False,
        message=f"Test not yet implemented for provider: {provider}",
    )

"""
Google Ads Offline Conversion Tracking (OCT) service.
"""
import hashlib
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional
import httpx
from fastapi import HTTPException
from app.config import settings

logger = logging.getLogger(__name__)

GCLID_MAX_AGE_DAYS = 90
GOOGLE_ADS_API_VERSION = "v17"
GOOGLE_ADS_BASE_URL = "https://googleads.googleapis.com"
TOKEN_URL = "https://oauth2.googleapis.com/token"

PERMANENT_ERROR_CODES = {
    "INVALID_ARGUMENT", "NOT_FOUND", "ALREADY_EXISTS", "PERMISSION_DENIED",
    "UNAUTHENTICATED", "CONVERSION_ADJUSTMENT_ALREADY_UPLOADED",
    "GCLID_NOT_FOUND", "INVALID_GCLID", "MISSING_REQUIRED_FIELDS",
}

CONTACT_FIELD_MAP = {
    "email_field": "email",
    "first_name_field": "first_name",
    "last_name_field": "last_name",
    "phone_field": "phone",
    "conversion_time_field": "conversion_synced_at",
    "conversion_value_field": "conversion_value",
}


async def get_access_token() -> str:
    if not settings.google_ads_refresh_token:
        raise HTTPException(status_code=503, detail="Google Ads not configured: GOOGLE_ADS_REFRESH_TOKEN missing")
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(TOKEN_URL, data={
            "client_id": settings.google_ads_client_id,
            "client_secret": settings.google_ads_client_secret,
            "refresh_token": settings.google_ads_refresh_token,
            "grant_type": "refresh_token",
        })
        if r.status_code != 200:
            logger.error(f"Google OAuth2 token refresh failed: {r.status_code} {r.text[:200]}")
            raise HTTPException(status_code=503, detail="Failed to refresh Google Ads access token")
        return r.json()["access_token"]


def _get_headers(access_token: str) -> dict:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "developer-token": settings.google_ads_developer_token,
        "Content-Type": "application/json",
    }
    # Only include login-customer-id when using a Manager (MCC) account
    manager_id = settings.google_ads_manager_customer_id
    if manager_id:
        headers["login-customer-id"] = manager_id.replace("-", "")
    return headers


def format_conversion_time(dt: datetime) -> str:
    """Format to Google Ads required format: 'yyyy-mm-dd hh:mm:ss+00:00'"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # Convert to UTC explicitly to ensure +00:00 suffix is accurate
    dt_utc = dt.astimezone(timezone.utc)
    return dt_utc.strftime("%Y-%m-%d %H:%M:%S+00:00")


def normalize_and_hash_email(email: str) -> str:
    """Normalize email per Google Enhanced Conversions spec, then SHA-256 hash."""
    normalized = email.lower().strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def normalize_and_hash_phone(phone: str) -> str:
    """Normalize phone to E.164 and SHA-256 hash for Enhanced Conversions."""
    digits = re.sub(r'[^\d]', '', phone)
    if len(digits) == 10:  # US number without country code
        e164 = f"+1{digits}"
    elif digits.startswith('1') and len(digits) == 11:
        e164 = f"+{digits}"
    else:
        e164 = f"+{digits}"
    return hashlib.sha256(e164.encode("utf-8")).hexdigest()


def hash_email(email: str) -> str:
    """Backward-compatible alias."""
    return normalize_and_hash_email(email)


def is_gclid_valid(gclid_captured_at: Optional[datetime]) -> bool:
    if not gclid_captured_at:
        return False
    if gclid_captured_at.tzinfo is None:
        gclid_captured_at = gclid_captured_at.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - gclid_captured_at
    return age.days <= GCLID_MAX_AGE_DAYS


def build_conversion_payload(
    gclid: str, conversion_action_id: str, conversion_time: datetime,
    conversion_value: float, email: Optional[str] = None, phone: Optional[str] = None,
    customer_id: Optional[str] = None,
) -> dict:
    cid = customer_id or settings.google_ads_customer_id
    payload = {
        "conversions": [{
            "gclid": gclid,
            "conversionAction": f"customers/{cid}/conversionActions/{conversion_action_id}",
            "conversionDateTime": format_conversion_time(conversion_time),
            "conversionValue": float(conversion_value or 0),
            "currencyCode": "USD",
        }],
        "partialFailure": True,
    }
    # Enhanced Conversions user identifiers
    user_identifiers = []
    if email and email.strip():
        user_identifiers.append({"hashedEmail": normalize_and_hash_email(email)})
    if phone and phone.strip():
        try:
            user_identifiers.append({"hashedPhoneNumber": normalize_and_hash_phone(phone)})
        except Exception:
            pass  # Phone normalization failed — skip it
    if user_identifiers:
        payload["conversions"][0]["userIdentifiers"] = user_identifiers
    return payload


async def upload_click_conversion(
    gclid: str, conversion_action_id: str, conversion_time: datetime,
    conversion_value: float = 0, email: Optional[str] = None,
    phone: Optional[str] = None,
) -> dict:
    if not settings.google_ads_customer_id:
        raise HTTPException(status_code=503, detail="GOOGLE_ADS_CUSTOMER_ID not configured")
    access_token = await get_access_token()
    cid = settings.google_ads_customer_id.replace("-", "")
    url = f"{GOOGLE_ADS_BASE_URL}/{GOOGLE_ADS_API_VERSION}/customers/{cid}:uploadClickConversions"
    payload = build_conversion_payload(gclid, conversion_action_id, conversion_time, conversion_value, email, phone)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, json=payload, headers=_get_headers(access_token))
        response_data = r.json() if r.content else {}
        if r.status_code == 200:
            partial_errors = response_data.get("partialFailureError", {})
            if partial_errors:
                error_details = partial_errors.get("details", [{}])
                error_code = _extract_error_code(error_details)
                return {"status": _classify_error(error_code), "response": response_data, "error": str(partial_errors), "error_code": error_code}
            return {"status": "success", "response": response_data, "error": None, "error_code": None}
        elif r.status_code in (429, 500, 502, 503, 504):
            return {"status": "transient_error", "response": response_data, "error": r.text[:500], "error_code": "UNAVAILABLE"}
        else:
            error_code = _extract_error_code(response_data.get("error", {}).get("details", [{}]))
            return {"status": "permanent_error", "response": response_data, "error": r.text[:500], "error_code": error_code}
    except httpx.TimeoutException:
        return {"status": "transient_error", "response": None, "error": "Request timed out", "error_code": "DEADLINE_EXCEEDED"}
    except Exception as e:
        logger.exception(f"Unexpected error uploading conversion: {e}")
        return {"status": "transient_error", "response": None, "error": str(e), "error_code": "INTERNAL"}


def upload_click_conversion_sync(
    gclid: str, conversion_action_id: str, conversion_time: datetime,
    conversion_value: float = 0.0, currency_code: str = "USD",
    email: Optional[str] = None, phone: Optional[str] = None,
) -> dict:
    """Synchronous version for use in Celery tasks."""
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(upload_click_conversion(
                gclid, conversion_action_id, conversion_time,
                conversion_value, email, phone,
            ))
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Sync upload failed: {e}")
        return {"status": "transient_error", "response": None, "error": str(e), "error_code": "INTERNAL"}


def _extract_error_code(details: list) -> str:
    try:
        return details[0].get("errors", [{}])[0].get("errorCode", {}).get("conversionUploadError", "UNKNOWN")
    except (IndexError, AttributeError, TypeError):
        return "UNKNOWN"


def _classify_error(error_code: str) -> str:
    return "permanent_error" if error_code in PERMANENT_ERROR_CODES else "transient_error"


def generate_tracking_snippet(config: dict) -> str:
    hidden_field_id = config.get("hidden_field_id", "gclid_field")
    cookie_name = config.get("cookie_name", "_sarson_gclid")
    return f"""<!-- Sarson Funds Google Ads GCLID Tracker -->
<script>
(function() {{
  var CONFIG = {{
    cookieName: '{cookie_name}',
    cookieDays: 90,
    hiddenFieldId: '{hidden_field_id}'
  }};
  function setCookie(name, value, days) {{
    var expires = new Date(Date.now() + days * 864e5).toUTCString();
    document.cookie = name + '=' + encodeURIComponent(value) + '; expires=' + expires + '; path=/; SameSite=Lax';
  }}
  function getCookie(name) {{
    return document.cookie.split('; ').reduce(function(r, v) {{
      var parts = v.split('=');
      return parts[0] === name ? decodeURIComponent(parts[1]) : r;
    }}, null);
  }}
  function getGCLIDFromURL() {{
    return new URLSearchParams(window.location.search).get('gclid');
  }}
  function injectGCLIDIntoForms(gclid) {{
    if (!gclid) return;
    var field = document.getElementById(CONFIG.hiddenFieldId);
    if (field) field.value = gclid;
    document.querySelectorAll('input[name="gclid"]').forEach(function(input) {{ input.value = gclid; }});
  }}
  var gclidFromURL = getGCLIDFromURL();
  if (gclidFromURL) setCookie(CONFIG.cookieName, gclidFromURL, CONFIG.cookieDays);
  var gclid = gclidFromURL || getCookie(CONFIG.cookieName);
  if (gclid) {{
    injectGCLIDIntoForms(gclid);
    document.addEventListener('DOMContentLoaded', function() {{ injectGCLIDIntoForms(gclid); }});
    if (window.MutationObserver) {{
      new MutationObserver(function() {{ injectGCLIDIntoForms(gclid); }}).observe(
        document.body || document.documentElement, {{ childList: true, subtree: true }}
      );
    }}
  }}
}})();
</script>"""

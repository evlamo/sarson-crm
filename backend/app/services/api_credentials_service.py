"""
Service for managing API credentials stored in the database.
Credentials are encrypted at rest using Fernet symmetric encryption.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Dict

from sqlalchemy.orm import Session

from app.models.api_credentials import ApiCredentials
from app.utils.encryption import encrypt_value, decrypt_value, mask_value

logger = logging.getLogger(__name__)

PROVIDER_FIELDS = {
    "mailchimp": {
        "api_key": {"label": "API Key", "sensitive": True, "placeholder": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx-us6", "help": "Found in Mailchimp → Account → Extras → API keys", "required": True},
        "server_prefix": {"label": "Server Prefix", "sensitive": False, "placeholder": "us6", "help": "Auto-detected from API key if left blank (the part after the last dash, e.g. 'us6')", "required": False},
        "audience_id": {"label": "Audience ID", "sensitive": False, "placeholder": "abc123def4", "help": "Mailchimp → Audience → Settings → Audience name and defaults → Audience ID", "required": True},
        "from_email": {"label": "Default From Email", "sensitive": False, "placeholder": "info@sarsonfunds.com", "help": "Must be a verified email in your Mailchimp account", "required": True},
        "from_name": {"label": "Default From Name", "sensitive": False, "placeholder": "Sarson Funds", "help": "Sender name shown in recipient inboxes", "required": True},
        "webhook_secret": {"label": "Webhook Secret", "sensitive": True, "placeholder": "random-secret-string", "help": "A secret token you generate — appended to Mailchimp webhook URL for verification", "required": False},
    }
}


def get_credentials(db: Session, provider: str) -> Optional[ApiCredentials]:
    return db.query(ApiCredentials).filter(ApiCredentials.provider == provider).first()


def get_decrypted_field(db: Session, provider: str, field: str) -> Optional[str]:
    creds = get_credentials(db, provider)
    if not creds or not creds.credentials:
        return None
    raw = creds.credentials.get(field, "")
    return decrypt_value(raw) if raw else None


def get_all_decrypted(db: Session, provider: str) -> Dict[str, str]:
    creds = get_credentials(db, provider)
    if not creds or not creds.credentials:
        return {}
    return {k: decrypt_value(v) for k, v in creds.credentials.items() if v}


def update_credentials(db: Session, provider: str, fields: Dict[str, Optional[str]]) -> ApiCredentials:
    creds = db.query(ApiCredentials).filter(ApiCredentials.provider == provider).first()
    if not creds:
        creds = ApiCredentials(provider=provider, credentials={})
        db.add(creds)

    current = dict(creds.credentials or {})

    for field, value in fields.items():
        if value is None:
            continue
        elif value == "":
            current.pop(field, None)
        else:
            current[field] = encrypt_value(value)

    creds.credentials = current
    provider_fields = PROVIDER_FIELDS.get(provider, {})
    required = [f for f, meta in provider_fields.items() if meta.get("required", True)]
    creds.is_configured = all(current.get(f) for f in required)
    creds.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(creds)
    return creds


def get_masked_fields(creds: ApiCredentials, provider: str) -> Dict[str, str]:
    if not creds or not creds.credentials:
        return {}
    provider_fields = PROVIDER_FIELDS.get(provider, {})
    result = {}
    for field, raw_encrypted in creds.credentials.items():
        if not raw_encrypted:
            continue
        decrypted = decrypt_value(raw_encrypted)
        field_def = provider_fields.get(field, {})
        if field_def.get("sensitive", True):
            result[field] = mask_value(decrypted, show_chars=4)
        else:
            result[field] = decrypted
    return result

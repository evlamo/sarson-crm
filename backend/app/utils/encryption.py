"""
Symmetric encryption for API credentials stored in the database.
Uses Fernet (AES-128-CBC + HMAC-SHA256) from the cryptography library.
Key is derived from SECRET_KEY in settings via SHA-256.

⚠️  WARNING: If SECRET_KEY changes, all encrypted credentials in the database
    will become permanently unreadable. Before changing SECRET_KEY:
    1. Export all credentials from the API Controls UI
    2. Change SECRET_KEY
    3. Re-enter credentials in the API Controls UI
"""
import base64
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _get_fernet():
    try:
        from cryptography.fernet import Fernet
        from app.config import settings
        key_bytes = hashlib.sha256(settings.secret_key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        return Fernet(fernet_key)
    except ImportError:
        logger.warning("cryptography package not installed — credentials stored as plaintext")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Fernet: {e}")
        return None


def encrypt_value(value: str) -> str:
    if not value:
        return value
    f = _get_fernet()
    if f is None:
        return value
    try:
        return f.encrypt(value.encode()).decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        return value


def decrypt_value(value: str) -> str:
    if not value:
        return value
    f = _get_fernet()
    if f is None:
        return value
    try:
        return f.decrypt(value.encode()).decode()
    except Exception:
        return value


def mask_value(value: str, show_chars: int = 4) -> str:
    if not value:
        return ""
    visible = value[:show_chars]
    return visible + "*" * min(8, max(0, len(value) - show_chars))

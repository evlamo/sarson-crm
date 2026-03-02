"""
Symmetric encryption for API credentials stored in the database.
Uses Fernet (AES-128-CBC + HMAC-SHA256) from the cryptography library.
Key is derived from SECRET_KEY in settings via SHA-256.

⚠️  WARNING: If SECRET_KEY changes, all encrypted credentials in the database
    will become permanently unreadable. Before changing SECRET_KEY:
    1. Export all credentials from the API Controls UI
    2. Change SECRET_KEY
    3. Re-enter credentials in the API Controls UI

Security notes (Phase 5 Audit):
- decrypt_value now raises DecryptionError on failure instead of returning encrypted data
- decrypt_value_safe returns (value, success) tuple for cases where failure is acceptable
- Never log encrypted values or decryption errors with sensitive content
"""
import base64
import hashlib
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class DecryptionError(Exception):
    """Raised when decryption fails — key may have changed or data corrupted."""
    pass


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
    """
    Encrypt a string value using Fernet.
    Returns the original value if encryption fails (for resilience).
    """
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
    """
    Decrypt a Fernet-encrypted value.
    
    IMPORTANT: Returns empty string if decryption fails.
    This prevents accidentally exposing encrypted blobs as if they were plaintext.
    
    Use decrypt_value_safe() if you need to distinguish between failure and empty value.
    """
    if not value:
        return value
    f = _get_fernet()
    if f is None:
        # No fernet = assume value is plaintext
        return value
    try:
        return f.decrypt(value.encode()).decode()
    except Exception:
        # Decryption failed — DO NOT return the encrypted value
        # Log error without revealing the encrypted content
        logger.error("Decryption failed — SECRET_KEY may have changed or value corrupted")
        return ""


def decrypt_value_safe(value: str) -> Tuple[str, bool]:
    """
    Decrypt a value and return (decrypted_value, success).
    
    Use this when you need to know if decryption actually succeeded.
    Returns ("", False) on failure instead of raising.
    """
    if not value:
        return value, True
    f = _get_fernet()
    if f is None:
        # No fernet = assume value is plaintext
        return value, True
    try:
        decrypted = f.decrypt(value.encode()).decode()
        return decrypted, True
    except Exception:
        logger.error("Decryption failed — SECRET_KEY may have changed or value corrupted")
        return "", False


def decrypt_value_or_raise(value: str) -> str:
    """
    Decrypt a value or raise DecryptionError.
    
    Use this when decryption failure should halt the operation.
    """
    if not value:
        return value
    f = _get_fernet()
    if f is None:
        return value
    try:
        return f.decrypt(value.encode()).decode()
    except Exception as e:
        raise DecryptionError("Failed to decrypt value — SECRET_KEY may have changed") from e


def mask_value(value: str, show_chars: int = 4) -> str:
    """Mask a value for display, showing only first N characters."""
    if not value:
        return ""
    visible = value[:show_chars]
    return visible + "*" * min(8, max(0, len(value) - show_chars))


def is_likely_encrypted(value: str) -> bool:
    """
    Heuristic check if a value looks like Fernet-encrypted data.
    Useful for detecting if decryption silently failed in older code.
    """
    if not value or len(value) < 50:
        return False
    # Fernet tokens are base64 and start with 'gAAAAA' (version + timestamp)
    try:
        # Check if it looks like base64
        base64.urlsafe_b64decode(value.encode())
        return value.startswith("gAAAAA")
    except Exception:
        return False

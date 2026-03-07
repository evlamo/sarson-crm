"""Service for encrypting/decrypting sensitive data."""

from app.auth.security import encrypt_data, decrypt_data


def encrypt_email(email: str) -> str:
    """Encrypt email address for storage."""
    if not email:
        return email
    return encrypt_data(email)


def decrypt_email(encrypted_email: str) -> str:
    """Decrypt email address from storage."""
    if not encrypted_email:
        return encrypted_email
    try:
        return decrypt_data(encrypted_email)
    except Exception:
        # If decryption fails, return as-is (already in plaintext)
        return encrypted_email


def encrypt_phone(phone: str) -> str:
    """Encrypt phone number for storage."""
    if not phone:
        return phone
    return encrypt_data(phone)


def decrypt_phone(encrypted_phone: str) -> str:
    """Decrypt phone number from storage."""
    if not encrypted_phone:
        return encrypted_phone
    try:
        return decrypt_data(encrypted_phone)
    except Exception:
        return encrypted_phone


def encrypt_sensitive_field(data: str) -> str:
    """Generic encryption for sensitive fields."""
    if not data:
        return data
    return encrypt_data(data)


def decrypt_sensitive_field(encrypted_data: str) -> str:
    """Generic decryption for sensitive fields."""
    if not encrypted_data:
        return encrypted_data
    try:
        return decrypt_data(encrypted_data)
    except Exception:
        return encrypted_data

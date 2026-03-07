from datetime import timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings
from app.utils.time import utcnow
import secrets
import string
import pyotp
import qrcode
from io import BytesIO
import base64
from cryptography.fernet import Fernet

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire, "type": "access", "jti": secrets.token_urlsafe(32)})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = utcnow() + timedelta(days=settings.refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh", "jti": secrets.token_urlsafe(32)})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)

def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])

def generate_reset_token() -> str:
    """Generate a secure password reset token."""
    return secrets.token_urlsafe(32)

def generate_email_verification_token() -> str:
    """Generate a secure email verification token."""
    return secrets.token_urlsafe(32)

def generate_totp_secret() -> str:
    """Generate a TOTP secret for MFA."""
    return pyotp.random_base32()

def verify_totp(secret: str, code: str) -> bool:
    """Verify a TOTP code against a secret."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)

def get_totp_qr_code(secret: str, email: str, issuer: str = "Sarson CRM") -> str:
    """Generate QR code URL for TOTP setup."""
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=email, issuer_name=issuer)
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode()

def generate_backup_codes(count: int = 10) -> list[str]:
    """Generate backup codes for MFA."""
    codes = []
    for _ in range(count):
        code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        codes.append(f"{code[:4]}-{code[4:]}")
    return codes

def encrypt_data(data: str) -> str:
    """Encrypt sensitive data using Fernet."""
    cipher = Fernet(settings.encryption_key.encode() if isinstance(settings.encryption_key, str) else settings.encryption_key)
    return cipher.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    """Decrypt sensitive data using Fernet."""
    cipher = Fernet(settings.encryption_key.encode() if isinstance(settings.encryption_key, str) else settings.encryption_key)
    return cipher.decrypt(encrypted_data.encode()).decode()

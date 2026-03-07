"""Tests for authentication security features."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.database import get_db
from app.models.user import User
from app.models.password_reset import PasswordResetToken
from app.models.email_verification import EmailVerificationToken
from app.models.mfa import MFASecret
from app.auth.security import hash_password, generate_reset_token, generate_totp_secret, verify_totp
from app.utils.time import utcnow
from datetime import timedelta
import uuid

client = TestClient(app)

# ==================== PASSWORD RESET TESTS ====================

def test_forgot_password_sends_reset_token(db: Session):
    """Test that forgot password endpoint creates reset token."""
    # Create test user
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        name="Test User",
        hashed_password=hash_password("password123"),
        role="user"
    )
    db.add(user)
    db.commit()
    
    # Request password reset
    response = client.post("/api/v1/auth/forgot-password", json={"email": "test@example.com"})
    assert response.status_code == 200
    assert "password reset link has been sent" in response.json()["message"]
    
    # Verify reset token was created
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id
    ).first()
    assert reset_token is not None
    assert reset_token.is_used == False
    assert reset_token.expires_at > utcnow()


def test_forgot_password_doesnt_reveal_user_exists(db: Session):
    """Test that forgot password doesn't reveal if user exists."""
    response = client.post("/api/v1/auth/forgot-password", json={"email": "nonexistent@example.com"})
    assert response.status_code == 200
    # Should return same message regardless
    assert "password reset link has been sent" in response.json()["message"]


def test_reset_password_with_valid_token(db: Session):
    """Test password reset with valid token."""
    # Create user and reset token
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        name="Test User",
        hashed_password=hash_password("password123"),
        role="user"
    )
    db.add(user)
    db.flush()
    
    reset_token = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token=generate_reset_token(),
        expires_at=utcnow() + timedelta(hours=24)
    )
    db.add(reset_token)
    db.commit()
    
    # Reset password
    response = client.post("/api/v1/auth/reset-password", json={
        "token": reset_token.token,
        "new_password": "NewPassword123"
    })
    assert response.status_code == 200
    
    # Verify token is marked as used
    db.refresh(reset_token)
    assert reset_token.is_used == True
    
    # Verify new password works
    response = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "NewPassword123"
    })
    assert response.status_code == 200


def test_reset_password_with_expired_token(db: Session):
    """Test password reset with expired token."""
    # Create expired reset token
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        name="Test User",
        hashed_password=hash_password("password123"),
        role="user"
    )
    db.add(user)
    db.flush()
    
    reset_token = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token=generate_reset_token(),
        expires_at=utcnow() - timedelta(hours=1)  # Expired
    )
    db.add(reset_token)
    db.commit()
    
    # Try to reset password
    response = client.post("/api/v1/auth/reset-password", json={
        "token": reset_token.token,
        "new_password": "NewPassword123"
    })
    assert response.status_code == 400
    assert "Invalid or expired" in response.json()["detail"]


# ==================== EMAIL VERIFICATION TESTS ====================

def test_register_requires_email_verification(db: Session):
    """Test that registered users need to verify email before login."""
    # Register new user
    response = client.post("/api/v1/auth/register", json={
        "email": "newuser@example.com",
        "name": "New User",
        "password": "Password123"
    })
    assert response.status_code == 201
    
    # Try to login without verifying email
    response = client.post("/api/v1/auth/login", json={
        "email": "newuser@example.com",
        "password": "Password123"
    })
    assert response.status_code == 403
    assert "verify your email" in response.json()["detail"]


def test_verify_email_with_valid_token(db: Session):
    """Test email verification with valid token."""
    # Create user with verification token
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        name="Test User",
        hashed_password=hash_password("password123"),
        role="user"
    )
    db.add(user)
    db.flush()
    
    verify_token = EmailVerificationToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token=generate_reset_token(),
        email="test@example.com",
        expires_at=utcnow() + timedelta(hours=24)
    )
    db.add(verify_token)
    db.commit()
    
    # Verify email
    response = client.post("/api/v1/auth/verify-email", json={"token": verify_token.token})
    assert response.status_code == 200
    
    # Verify token is marked as verified
    db.refresh(verify_token)
    assert verify_token.is_verified == True


# ==================== MFA TESTS ====================

def test_mfa_setup_generates_secret(db: Session):
    """Test MFA setup generates secret and QR code."""
    # Create and login user
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        name="Test User",
        hashed_password=hash_password("password123"),
        role="admin"
    )
    db.add(user)
    db.commit()
    
    # Login
    login_response = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "password123"
    })
    token = login_response.json()["access_token"]
    
    # Setup MFA
    response = client.post("/api/v1/auth/mfa/setup", 
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "secret" in data
    assert "qr_code_url" in data
    assert "backup_codes" in data
    assert len(data["backup_codes"]) > 0


def test_mfa_enable_with_valid_code(db: Session):
    """Test MFA enablement with valid TOTP code."""
    # Create user and MFA secret
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        name="Test User",
        hashed_password=hash_password("password123"),
        role="admin"
    )
    db.add(user)
    db.flush()
    
    secret = generate_totp_secret()
    from app.auth.security import encrypt_data
    mfa_secret = MFASecret(
        id=uuid.uuid4(),
        user_id=user.id,
        secret_key=encrypt_data(secret),
        is_enabled=False
    )
    db.add(mfa_secret)
    db.commit()
    
    # Login
    login_response = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "password123"
    })
    token = login_response.json()["access_token"]
    
    # Get valid TOTP code
    import pyotp
    totp = pyotp.TOTP(secret)
    valid_code = totp.now()
    
    # Enable MFA
    response = client.post("/api/v1/auth/mfa/enable",
        json={"code": valid_code, "password": "password123"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    
    # Verify MFA is enabled
    db.refresh(mfa_secret)
    assert mfa_secret.is_enabled == True


# ==================== TOKEN REVOCATION TESTS ====================

def test_logout_revokes_token(db: Session):
    """Test that logout revokes access token."""
    # Create and login user
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        name="Test User",
        hashed_password=hash_password("password123"),
        role="user"
    )
    db.add(user)
    db.commit()
    
    # Login
    login_response = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "password123"
    })
    token = login_response.json()["access_token"]
    
    # Logout
    response = client.post("/api/v1/auth/logout",
        json={},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200


# ==================== RATE LIMITING TESTS ====================

def test_register_rate_limiting():
    """Test that register endpoint has rate limiting."""
    # Make multiple requests rapidly
    responses = []
    for i in range(6):
        response = client.post("/api/v1/auth/register", json={
            "email": f"user{i}@example.com",
            "name": "Test User",
            "password": "Password123"
        })
        responses.append(response.status_code)
    
    # After 5 requests in a minute, should be rate limited
    assert any(status == 429 for status in responses), "Rate limiting should be enforced"


def test_refresh_rate_limiting(db: Session):
    """Test that refresh endpoint has rate limiting."""
    # Create user
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        name="Test User",
        hashed_password=hash_password("password123"),
        role="user"
    )
    db.add(user)
    db.commit()
    
    # Login to get refresh token
    login_response = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "password123"
    })
    refresh_token = login_response.json()["refresh_token"]
    
    # Make multiple refresh requests
    responses = []
    for _ in range(11):
        response = client.post("/api/v1/auth/refresh", 
            json={"refresh_token": refresh_token}
        )
        responses.append(response.status_code)
    
    # After 10 requests in a minute, should be rate limited
    assert any(status == 429 for status in responses), "Rate limiting should be enforced"

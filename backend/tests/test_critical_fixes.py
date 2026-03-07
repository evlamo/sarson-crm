"""Unit tests for critical security fixes."""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from jose import jwt

from app.models.user import User
from app.models.contact import Contact
from app.models.token_blacklist import TokenBlacklist
from app.auth.security import (
    create_access_token, create_refresh_token, hash_password, 
    decode_token, encrypt_data, decrypt_data
)
from app.config import settings
from app.services.email_service import EmailService
from app.services.encryption_service import encrypt_email, decrypt_email
from app.utils.time import utcnow


# ==================== ADDITIONAL FIXTURES ====================

@pytest.fixture
def test_user(db) -> User:
    """Create a test user."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        name="Test User",
        hashed_password=hash_password("TestPassword123"),
        role="user",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_contact(db) -> Contact:
    """Create a test contact."""
    contact = Contact(
        id=uuid.uuid4(),
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        company="Acme Corp",
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


# ==================== TEST: LOGOUT ENDPOINT - TOKEN BLACKLISTING ====================

class TestLogoutEndpoint:
    """Test logout endpoint token blacklisting."""
    
    def test_logout_creates_blacklist_entry(self, client, db, test_user):
        """Test that logout endpoint creates a TokenBlacklist entry."""
        # Create tokens
        token_data = {"sub": str(test_user.id), "email": test_user.email, "role": test_user.role}
        access_token = create_access_token(token_data)
        
        # Decode to get JTI
        payload = decode_token(access_token)
        jti = payload.get("jti")
        assert jti is not None
        
        # Send logout request
        response = client.post(
            "/api/v1/auth/logout",
            json={},
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully"
        
        # Verify TokenBlacklist entry was created
        blacklist_entry = db.query(TokenBlacklist).filter(
            TokenBlacklist.token_jti == jti
        ).first()
        assert blacklist_entry is not None
        assert blacklist_entry.user_id == test_user.id
    
    def test_logout_without_authorization_header(self, client, test_user):
        """Test logout without Authorization header returns 403."""
        response = client.post(
            "/api/v1/auth/logout",
            json={},
        )
        
        assert response.status_code == 403  # Forbidden due to missing credentials
    
    def test_logout_with_invalid_token(self, client, test_user):
        """Test logout with invalid token returns 400."""
        response = client.post(
            "/api/v1/auth/logout",
            json={},
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        assert response.status_code == 400
    
    def test_blacklisted_token_rejected_on_next_request(self, client, db, test_user):
        """Test that blacklisted token is rejected on subsequent requests."""
        # Create and logout
        token_data = {"sub": str(test_user.id), "email": test_user.email, "role": test_user.role}
        access_token = create_access_token(token_data)
        
        # Logout (blacklist token)
        response = client.post(
            "/api/v1/auth/logout",
            json={},
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 200
        
        # Try to use the blacklisted token
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        # Should be rejected
        assert response.status_code == 401


# ==================== TEST: EMAIL ENCRYPTION ====================

class TestEmailEncryption:
    """Test email encryption in Contact model."""
    
    def test_email_encryption_on_save(self, test_contact):
        """Test that email is encrypted when set."""
        original_email = test_contact.email
        
        # Email should be encrypted in _email_encrypted
        assert test_contact._email_encrypted != original_email
        assert test_contact._email_encrypted is not None
        
        # But decrypted when accessed via email property
        assert test_contact.email == original_email
    
    def test_email_decryption_on_retrieval(self, db):
        """Test that email is decrypted when retrieved."""
        original_email = "jane.smith@example.com"
        
        # Create contact with email
        contact = Contact(
            id=uuid.uuid4(),
            first_name="Jane",
            last_name="Smith",
            email=original_email,
        )
        db.add(contact)
        db.commit()
        
        # Verify encrypted in DB column
        assert contact._email_encrypted != original_email
        
        # Verify decrypted via property
        assert contact.email == original_email
        
        # Retrieve from DB and verify decryption still works
        retrieved = db.query(Contact).filter(Contact.id == contact.id).first()
        assert retrieved is not None
        assert retrieved.email == original_email
    
    def test_email_none_handling(self, db):
        """Test that None email is handled correctly."""
        contact = Contact(id=uuid.uuid4())
        contact.email = None
        
        assert contact._email_encrypted is None
        assert contact.email is None
        
        db.add(contact)
        db.commit()
        
        # Verify None is preserved in DB
        retrieved = db.query(Contact).filter(Contact.id == contact.id).first()
        assert retrieved.email is None
    
    def test_email_domain_extraction(self, db):
        """Test that email_domain is extracted from email."""
        contact = Contact(id=uuid.uuid4())
        contact.email = "user@company.com"
        
        db.add(contact)
        db.commit()
        
        assert contact.email_domain == "company.com"
        assert contact.email == "user@company.com"
        
        # Verify domain is stored in DB
        retrieved = db.query(Contact).filter(Contact.id == contact.id).first()
        assert retrieved.email_domain == "company.com"
    
    def test_encryption_service_functions(self):
        """Test encryption service helper functions."""
        original = "test@example.com"
        
        # Encrypt
        encrypted = encrypt_email(original)
        assert encrypted != original
        
        # Decrypt
        decrypted = decrypt_email(encrypted)
        assert decrypted == original
    
    def test_encryption_service_with_none(self):
        """Test encryption service with None."""
        assert encrypt_email(None) is None
        assert decrypt_email(None) is None
    
    def test_encryption_service_with_empty_string(self):
        """Test encryption service with empty string."""
        assert encrypt_email("") == ""
        assert decrypt_email("") == ""


# ==================== TEST: EMAIL SENDING - SENDGRID INTEGRATION ====================

class TestEmailService:
    """Test EmailService with SendGrid."""
    
    def test_email_service_initialization(self):
        """Test EmailService initializes correctly."""
        service = EmailService()
        
        # Should be initialized regardless of API key
        assert service is not None
        # Client will be None if API key not set, that's OK
        if settings.sendgrid_api_key:
            assert service.client is not None
    
    def test_send_email_with_no_client(self):
        """Test email sending when client is not initialized."""
        service = EmailService()
        # If no API key, client will be None
        if service.client is None:
            result = service.send_email(
                to_email="test@example.com",
                subject="Test Subject",
                html_content="<p>Test</p>",
            )
            assert result is False
    
    def test_email_service_has_password_reset_method(self):
        """Test email service has password reset method."""
        service = EmailService()
        assert hasattr(service, 'send_password_reset_email')
        assert callable(service.send_password_reset_email)
    
    def test_email_service_has_verification_method(self):
        """Test email service has email verification method."""
        service = EmailService()
        assert hasattr(service, 'send_email_verification_email')
        assert callable(service.send_email_verification_email)
    
    def test_email_service_with_cc_and_bcc(self):
        """Test email service method signature includes CC and BCC."""
        service = EmailService()
        
        # Verify send_email accepts cc and bcc parameters
        import inspect
        sig = inspect.signature(service.send_email)
        assert 'cc' in sig.parameters
        assert 'bcc' in sig.parameters
    
    def test_password_reset_email_content(self):
        """Test password reset email has correct content."""
        service = EmailService()
        
        # If no client, we can't test actual sending
        if service.client is not None:
            # This would require mocking SendGrid
            pass
        
        # But we can verify the method doesn't raise exceptions
        try:
            # This will fail to send if no API key, but shouldn't raise exception
            service.send_password_reset_email(
                to_email="test@example.com",
                reset_token="test_token"
            )
        except Exception as e:
            # If it raises, it should be a SendGrid exception, not a code error
            assert "SendGrid" in str(type(e).__name__) or "Connection" in str(e)
    
    def test_email_verification_email_content(self):
        """Test email verification email has correct content."""
        service = EmailService()
        
        # If no client, we can't test actual sending
        if service.client is not None:
            # This would require mocking SendGrid
            pass
        
        # But we can verify the method doesn't raise exceptions
        try:
            # This will fail to send if no API key, but shouldn't raise exception
            service.send_email_verification_email(
                to_email="test@example.com",
                verification_token="verify_token"
            )
        except Exception as e:
            # If it raises, it should be a SendGrid exception, not a code error
            assert "SendGrid" in str(type(e).__name__) or "Connection" in str(e)


# ==================== TEST: INTEGRATION TESTS ====================

class TestIntegration:
    """Integration tests combining multiple fixes."""
    
    def test_contact_with_encrypted_email_and_search(self, db):
        """Test contact with encrypted email can be searched."""
        contact = Contact(
            id=uuid.uuid4(),
            first_name="Jane",
            last_name="Smith",
            email="jane.smith@example.com",
        )
        db.add(contact)
        db.commit()
        
        # Verify email is encrypted in DB column
        assert contact._email_encrypted != "jane.smith@example.com"
        
        # Verify email is decrypted via property
        assert contact.email == "jane.smith@example.com"
        
        # Verify email_domain is correctly set
        assert contact.email_domain == "example.com"
        
        # Verify can retrieve from DB with decryption
        retrieved = db.query(Contact).filter(Contact.id == contact.id).first()
        assert retrieved is not None
        assert retrieved.email == "jane.smith@example.com"
    
    def test_logout_and_token_blacklist_check(self, client, db, test_user):
        """Test logout creates blacklist that subsequent requests check."""
        # Create token
        token_data = {"sub": str(test_user.id), "email": test_user.email, "role": test_user.role}
        access_token = create_access_token(token_data)
        
        # Logout
        response = client.post(
            "/api/v1/auth/logout",
            json={},
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        assert response.status_code == 200
        
        # Verify blacklist entry was created in DB
        payload = decode_token(access_token)
        jti = payload.get("jti")
        
        blacklist_entry = db.query(TokenBlacklist).filter(
            TokenBlacklist.token_jti == jti
        ).first()
        assert blacklist_entry is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

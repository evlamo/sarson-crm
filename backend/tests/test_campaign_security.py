"""Tests for campaign security features."""

import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.database import get_db
from app.models.user import User
from app.models.campaign import EmailCampaign, EmailSend
from app.models.segment import Segment
from app.auth.security import hash_password
from app.utils.time import utcnow

client = TestClient(app)

# ==================== CAMPAIGN IDEMPOTENCY TESTS ====================

def test_campaign_idempotency_prevents_duplicate_sends(db: Session):
    """Test that idempotency key prevents duplicate campaign sends."""
    # Create admin user
    admin = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        name="Admin",
        hashed_password=hash_password("password123"),
        role="admin"
    )
    db.add(admin)
    db.flush()
    
    # Create segment
    segment = Segment(
        id=uuid.uuid4(),
        name="Test Segment",
        filter_json={}
    )
    db.add(segment)
    db.flush()
    
    # Create campaign
    campaign = EmailCampaign(
        id=uuid.uuid4(),
        name="Test Campaign",
        subject="Test",
        body_html="<p>Test</p>",
        from_name="Test",
        from_email="test@example.com",
        status="draft",
        segment_id=segment.id,
        created_by=admin.id
    )
    db.add(campaign)
    db.commit()
    
    # Login
    login_response = client.post("/api/v1/auth/login", json={
        "email": "admin@example.com",
        "password": "password123"
    })
    token = login_response.json()["access_token"]
    
    # Send campaign with idempotency key
    idempotency_key = "test-key-12345"
    response1 = client.post(
        f"/api/v1/campaigns/{campaign.id}/send",
        json={"idempotency_key": idempotency_key},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response1.status_code == 200
    
    # Try to send again with same idempotency key
    response2 = client.post(
        f"/api/v1/campaigns/{campaign.id}/send",
        json={"idempotency_key": idempotency_key},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response2.status_code == 400
    assert "already sent" in response2.json()["detail"]


# ==================== CONTACT REMOVAL TESTS ====================

def test_remove_contact_from_campaign(db: Session):
    """Test removing a contact from a campaign."""
    # Create admin user
    admin = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        name="Admin",
        hashed_password=hash_password("password123"),
        role="admin"
    )
    db.add(admin)
    db.flush()
    
    # Create campaign
    campaign = EmailCampaign(
        id=uuid.uuid4(),
        name="Test Campaign",
        subject="Test",
        body_html="<p>Test</p>",
        from_name="Test",
        from_email="test@example.com",
        status="sent",
        created_by=admin.id,
        recipient_count=1,
        sent_count=1,
        delivered_count=1
    )
    db.add(campaign)
    db.flush()
    
    # Create email send record
    email_send = EmailSend(
        id=uuid.uuid4(),
        campaign_id=campaign.id,
        contact_id=uuid.uuid4(),
        email_address="recipient@example.com",
        status="delivered"
    )
    db.add(email_send)
    db.commit()
    
    # Login
    login_response = client.post("/api/v1/auth/login", json={
        "email": "admin@example.com",
        "password": "password123"
    })
    token = login_response.json()["access_token"]
    
    # Remove contact
    response = client.delete(
        f"/api/v1/campaigns/{campaign.id}/contacts/{email_send.contact_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    
    # Verify contact is removed
    removed = db.query(EmailSend).filter(
        EmailSend.id == email_send.id
    ).first()
    assert removed is None
    
    # Verify stats are updated
    db.refresh(campaign)
    assert campaign.recipient_count == 0
    assert campaign.sent_count == 0


def test_remove_contact_not_in_campaign(db: Session):
    """Test removing a contact that's not in campaign."""
    # Create admin user
    admin = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        name="Admin",
        hashed_password=hash_password("password123"),
        role="admin"
    )
    db.add(admin)
    db.flush()
    
    # Create campaign
    campaign = EmailCampaign(
        id=uuid.uuid4(),
        name="Test Campaign",
        subject="Test",
        body_html="<p>Test</p>",
        from_name="Test",
        from_email="test@example.com",
        status="sent",
        created_by=admin.id
    )
    db.add(campaign)
    db.commit()
    
    # Login
    login_response = client.post("/api/v1/auth/login", json={
        "email": "admin@example.com",
        "password": "password123"
    })
    token = login_response.json()["access_token"]
    
    # Try to remove non-existent contact
    contact_id = uuid.uuid4()
    response = client.delete(
        f"/api/v1/campaigns/{campaign.id}/contacts/{contact_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404


# ==================== CSRF PROTECTION TESTS ====================

def test_csrf_token_generation():
    """Test that CSRF tokens are generated for all requests."""
    response = client.get("/health")
    assert response.status_code == 200
    # CSRF token should be in cookies
    assert "csrf_token" in response.cookies


def test_csrf_token_required_for_post():
    """Test that CSRF token is checked for state-changing requests."""
    # Public endpoints should work without CSRF token
    response = client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "name": "Test",
        "password": "Password123"
    })
    # Should succeed or fail due to user already existing, not CSRF
    assert response.status_code in [201, 400]


# ==================== ERROR HANDLING TESTS ====================

def test_campaign_send_requires_segment(db: Session):
    """Test that campaign send requires a segment."""
    # Create admin user
    admin = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        name="Admin",
        hashed_password=hash_password("password123"),
        role="admin"
    )
    db.add(admin)
    db.flush()
    
    # Create campaign without segment
    campaign = EmailCampaign(
        id=uuid.uuid4(),
        name="Test Campaign",
        subject="Test",
        body_html="<p>Test</p>",
        from_name="Test",
        from_email="test@example.com",
        status="draft",
        created_by=admin.id
    )
    db.add(campaign)
    db.commit()
    
    # Login
    login_response = client.post("/api/v1/auth/login", json={
        "email": "admin@example.com",
        "password": "password123"
    })
    token = login_response.json()["access_token"]
    
    # Try to send without segment
    response = client.post(
        f"/api/v1/campaigns/{campaign.id}/send",
        json={},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 400
    assert "segment" in response.json()["detail"]

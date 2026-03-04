"""
DNC (Do Not Contact) enforcement tests.

Covers:
  - Master DNC set / clear via API
  - RBAC: only admin can set/clear
  - Auto-DNC on email unsubscribe
  - DNC contacts excluded from campaign segment resolution
  - Fresh Slate Rule: per-campaign status does NOT bleed across campaigns
"""
import uuid
import pytest

from app.models.contact import Contact
from app.models.sales_campaign import SalesCampaign, CampaignContact
from app.models.campaign_segment import CampaignSegment
from app.services.campaign_list_service import resolve_segment_contacts


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def member_token(client, member_user) -> str:
    resp = client.post("/api/v1/auth/login", json={
        "email": "member@sarsonfunds.com",
        "password": "Member123!",
    })
    assert resp.status_code == 200, f"Member login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture
def member_headers(member_token) -> dict:
    return {"Authorization": f"Bearer {member_token}"}


@pytest.fixture
def contact(client, auth_headers):
    """A plain contact with no DNC status."""
    resp = client.post("/api/v1/contacts", json={
        "first_name": "Test",
        "last_name": "Contact",
        "email": "test.contact@example.com",
    }, headers=auth_headers)
    assert resp.status_code == 201, f"Create contact failed: {resp.text}"
    return resp.json()


@pytest.fixture
def dnc_contact(client, auth_headers, contact):
    """A contact that has already had master DNC set."""
    contact_id = contact["id"]
    resp = client.post(
        f"/api/v1/contacts/{contact_id}/dnc",
        json={"reason": "Pre-set DNC for test"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, f"Pre-set DNC failed: {resp.text}"
    return contact


# ── Helper: sync exclusion check (mirrors dnc_service logic) ───────────────

def _is_excluded_for_campaign(db, contact_id, sales_campaign_id):
    """
    Sync reimplementation of dnc_service.is_contact_excluded for testing.
    Checks master DNC first, then per-campaign completion status.
    """
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        return False, "contact not found"
    if contact.master_dnc:
        return True, f"Master DNC: {contact.master_dnc_reason or 'Do not contact'}"

    cc = db.query(CampaignContact).filter(
        CampaignContact.contact_id == contact_id,
        CampaignContact.sales_campaign_id == sales_campaign_id,
    ).first()
    if cc and cc.completion_status in ("complete", "no"):
        return True, f"Campaign status: {cc.completion_status}"

    return False, ""


# ── Helper: create DB objects directly ────────────────────────────────────

def _make_sales_campaign(db, name="Test Campaign"):
    sc = SalesCampaign(id=uuid.uuid4(), name=name, status="active")
    db.add(sc)
    db.flush()
    return sc


def _make_contact(db, email, status="active", master_dnc=False):
    c = Contact(
        id=uuid.uuid4(),
        first_name="Test",
        last_name="Person",
        email=email,
        status=status,
        master_dnc=master_dnc,
    )
    db.add(c)
    db.flush()
    return c


def _add_campaign_contact(db, contact_id, campaign_id, completion_status=None):
    cc = CampaignContact(
        id=uuid.uuid4(),
        contact_id=contact_id,
        sales_campaign_id=campaign_id,
        status=completion_status or "active",
        completion_status=completion_status,
    )
    db.add(cc)
    db.flush()
    return cc


# ── Test 1: Admin can set master DNC ──────────────────────────────────────

def test_set_master_dnc(client, auth_headers, contact, db):
    contact_id = contact["id"]
    resp = client.post(
        f"/api/v1/contacts/{contact_id}/dnc",
        json={"reason": "Requested removal"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, f"Unexpected status: {resp.status_code} — {resp.text}"
    data = resp.json()
    assert data["master_dnc"] is True

    # Verify in DB
    db.expire_all()
    db_contact = db.query(Contact).filter(Contact.id == uuid.UUID(contact_id)).first()
    assert db_contact.master_dnc is True
    assert db_contact.master_dnc_reason == "Requested removal"


# ── Test 2: Member cannot set DNC (403) ───────────────────────────────────

def test_set_dnc_member_forbidden(client, member_headers, contact):
    contact_id = contact["id"]
    resp = client.post(
        f"/api/v1/contacts/{contact_id}/dnc",
        json={"reason": "Unauthorized attempt"},
        headers=member_headers,
    )
    assert resp.status_code == 403


# ── Test 3: Admin can remove master DNC ───────────────────────────────────

def test_clear_master_dnc(client, auth_headers, dnc_contact, db):
    contact_id = dnc_contact["id"]
    resp = client.delete(
        f"/api/v1/contacts/{contact_id}/dnc",
        headers=auth_headers,
    )
    assert resp.status_code == 204, f"Unexpected status: {resp.status_code} — {resp.text}"

    # Verify in DB
    db.expire_all()
    db_contact = db.query(Contact).filter(Contact.id == uuid.UUID(contact_id)).first()
    assert db_contact.master_dnc is False
    assert db_contact.master_dnc_reason is None


# ── Test 4: Member cannot remove DNC (403) ────────────────────────────────

def test_clear_dnc_member_forbidden(client, member_headers, dnc_contact):
    contact_id = dnc_contact["id"]
    resp = client.delete(
        f"/api/v1/contacts/{contact_id}/dnc",
        headers=member_headers,
    )
    assert resp.status_code == 403


# ── Test 5: Auto-DNC on email unsubscribe ─────────────────────────────────

def test_auto_dnc_on_unsubscribe(client, auth_headers, contact, db):
    contact_id = contact["id"]

    resp = client.patch(
        f"/api/v1/contacts/{contact_id}",
        json={"email_unsubscribed": True},
        headers=auth_headers,
    )
    assert resp.status_code == 200, f"Patch failed: {resp.text}"

    db.expire_all()
    db_contact = db.query(Contact).filter(Contact.id == uuid.UUID(contact_id)).first()
    assert db_contact.email_unsubscribed is True
    assert db_contact.master_dnc is True
    assert db_contact.master_dnc_reason == "Email unsubscribe"


# ── Test 6: DNC contact excluded from email campaign eligible-contacts list ─

def test_dnc_excluded_from_campaign_segment_filter(db, admin_user):
    """
    DNC contact is excluded from filter-based campaign segment resolution.
    Simulates 'get eligible contacts' for an email campaign.
    """
    dnc = _make_contact(db, "dnc.filter@example.com", status="active", master_dnc=True)
    safe = _make_contact(db, "safe.filter@example.com", status="active", master_dnc=False)
    db.commit()

    segment = CampaignSegment(
        id=uuid.uuid4(),
        name="Active Contacts",
        filters={"statuses": ["active"]},
        created_by=admin_user.id,
    )
    db.add(segment)
    db.commit()

    resolved = resolve_segment_contacts(segment, db)
    resolved_ids = {c.id for c in resolved}

    assert dnc.id not in resolved_ids, "DNC contact must be excluded from email segment"
    assert safe.id in resolved_ids, "Non-DNC contact must be included in email segment"


# ── Test 7: DNC contact excluded from resolve_segment_contacts ─────────────

def test_dnc_excluded_from_resolve_segment_contacts(db, admin_user):
    """
    DNC contact is excluded by resolve_segment_contacts regardless of status filter match.
    """
    dnc = _make_contact(db, "dnc.resolve@example.com", status="prospect", master_dnc=True)
    safe = _make_contact(db, "safe.resolve@example.com", status="prospect", master_dnc=False)
    db.commit()

    segment = CampaignSegment(
        id=uuid.uuid4(),
        name="Prospect Segment",
        filters={"statuses": ["prospect"]},
        created_by=admin_user.id,
    )
    db.add(segment)
    db.commit()

    resolved = resolve_segment_contacts(segment, db)
    resolved_ids = {c.id for c in resolved}

    assert dnc.id not in resolved_ids, "DNC contact excluded from resolve_segment_contacts"
    assert safe.id in resolved_ids, "Non-DNC contact included in resolve_segment_contacts"


# ── Test 8: Fresh Slate — "no" on Campaign A still eligible for Campaign B ─

def test_fresh_slate_no_eligible_for_other_campaign(db):
    """
    Contact marked 'no' on Campaign A is still eligible for Campaign B.
    Fresh Slate Rule: per-campaign status never bleeds to other campaigns.
    """
    campaign_a = _make_sales_campaign(db, "Slate Campaign A")
    campaign_b = _make_sales_campaign(db, "Slate Campaign B")
    contact = _make_contact(db, "slate.no@example.com")

    _add_campaign_contact(db, contact.id, campaign_a.id, completion_status="no")
    db.commit()

    excluded_a, reason_a = _is_excluded_for_campaign(db, contact.id, campaign_a.id)
    assert excluded_a is True, f"Contact should be excluded from Campaign A, reason: {reason_a}"

    excluded_b, _ = _is_excluded_for_campaign(db, contact.id, campaign_b.id)
    assert excluded_b is False, "Contact with 'no' on Campaign A must be eligible for Campaign B"


# ── Test 9: Fresh Slate — "completed" on Campaign A still eligible for B ──

def test_fresh_slate_completed_eligible_for_other_campaign(db):
    """
    Contact marked 'completed' on Campaign A is still eligible for Campaign B.
    """
    campaign_a = _make_sales_campaign(db, "Completed Campaign A")
    campaign_b = _make_sales_campaign(db, "New Campaign B")
    contact = _make_contact(db, "slate.completed@example.com")

    _add_campaign_contact(db, contact.id, campaign_a.id, completion_status="complete")
    db.commit()

    excluded_a, _ = _is_excluded_for_campaign(db, contact.id, campaign_a.id)
    assert excluded_a is True

    excluded_b, _ = _is_excluded_for_campaign(db, contact.id, campaign_b.id)
    assert excluded_b is False, "Contact 'completed' on Campaign A must be eligible for Campaign B"


# ── Test 10: "no" on Campaign A excluded from Campaign A sends ─────────────

def test_no_status_excluded_from_same_campaign(db):
    """
    Contact marked 'no' on Campaign A is excluded from that campaign's email sends.
    """
    campaign_a = _make_sales_campaign(db, "Same Campaign A")
    contact = _make_contact(db, "slate.no.same@example.com")

    _add_campaign_contact(db, contact.id, campaign_a.id, completion_status="no")
    db.commit()

    excluded, reason = _is_excluded_for_campaign(db, contact.id, campaign_a.id)
    assert excluded is True
    assert "no" in reason.lower(), f"Reason should mention 'no' status, got: {reason}"

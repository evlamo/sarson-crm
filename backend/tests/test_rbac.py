"""
RBAC (Role-Based Access Control) tests.

Verifies that every admin-only endpoint returns:
  - 200/201/204 for admin
  - 403 for authenticated member
  - 401 for unauthenticated requests

Endpoints covered:
  1.  GET  /api/v1/users/
  2.  POST /api/v1/users/
  3.  PATCH /api/v1/users/{id}/deactivate
  4.  POST /api/v1/contacts/bulk-delete
  5.  DELETE /api/v1/lists/{id}
  6.  POST /api/v1/invites/
  7.  GET  /api/v1/invites/
  8.  POST /api/v1/contacts/{id}/dnc
  9.  DELETE /api/v1/contacts/{id}/dnc
  10. POST /api/v1/campaigns
"""
import uuid
import pytest

from app.models.contact import Contact
from app.models.static_list import StaticList


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
def a_contact(client, auth_headers):
    """A plain contact created by admin for use in RBAC tests."""
    resp = client.post("/api/v1/contacts", json={
        "first_name": "RBAC",
        "last_name": "Test",
        "email": f"rbac.{uuid.uuid4().hex[:8]}@example.com",
    }, headers=auth_headers)
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
def a_dnc_contact(client, auth_headers, a_contact):
    """A contact that already has master DNC set."""
    contact_id = a_contact["id"]
    resp = client.post(
        f"/api/v1/contacts/{contact_id}/dnc",
        json={"reason": "RBAC test pre-set"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, f"Pre-set DNC failed: {resp.text}"
    return a_contact


@pytest.fixture
def a_list(db, admin_user):
    """A StaticList created directly in DB for delete tests."""
    sl = StaticList(
        id=uuid.uuid4(),
        name="RBAC Test List",
        created_by=admin_user.id,
    )
    db.add(sl)
    db.commit()
    return sl


# ── Helper: unique email ──────────────────────────────────────────────────

def _unique_email(prefix="rbac"):
    return f"{prefix}.{uuid.uuid4().hex[:8]}@example.com"


# ── 1. GET /api/v1/users/ ─────────────────────────────────────────────────

def test_list_users_admin_success(client, auth_headers, admin_user):
    resp = client.get("/api/v1/users/", headers=auth_headers)
    assert resp.status_code == 200


def test_list_users_member_forbidden(client, member_headers, member_user):
    resp = client.get("/api/v1/users/", headers=member_headers)
    assert resp.status_code == 403


def test_list_users_unauthenticated(client):
    resp = client.get("/api/v1/users/")
    assert resp.status_code == 401


# ── 2. POST /api/v1/users/ ────────────────────────────────────────────────

def test_create_user_admin_success(client, auth_headers, admin_user):
    resp = client.post("/api/v1/users/", json={
        "email": _unique_email("newuser"),
        "name": "New User",
        "password": "Secure123!",
        "role": "member",
    }, headers=auth_headers)
    assert resp.status_code == 200  # endpoint has no status_code=201 set


def test_create_user_member_forbidden(client, member_headers, member_user):
    resp = client.post("/api/v1/users/", json={
        "email": _unique_email("newuser"),
        "name": "New User",
        "password": "Secure123!",
        "role": "member",
    }, headers=member_headers)
    assert resp.status_code == 403


def test_create_user_unauthenticated(client):
    resp = client.post("/api/v1/users/", json={
        "email": _unique_email("newuser"),
        "name": "New User",
        "password": "Secure123!",
        "role": "member",
    })
    assert resp.status_code == 401


# ── 3. PATCH /api/v1/users/{id}/deactivate ────────────────────────────────

def test_deactivate_user_admin_success(client, auth_headers, admin_user, member_user):
    # Admin deactivates the member (not themselves)
    resp = client.patch(
        f"/api/v1/users/{member_user.id}/deactivate",
        headers=auth_headers,
    )
    assert resp.status_code == 200


def test_deactivate_user_member_forbidden(client, member_headers, admin_user, member_user):
    resp = client.patch(
        f"/api/v1/users/{admin_user.id}/deactivate",
        headers=member_headers,
    )
    assert resp.status_code == 403


def test_deactivate_user_unauthenticated(client, admin_user, member_user):
    resp = client.patch(f"/api/v1/users/{member_user.id}/deactivate")
    assert resp.status_code == 401


# ── 4. POST /api/v1/contacts/bulk-delete ─────────────────────────────────

def test_bulk_delete_admin_success(client, auth_headers, admin_user, a_contact):
    resp = client.post(
        "/api/v1/contacts/bulk-delete",
        json={"ids": [a_contact["id"]]},
        headers=auth_headers,
    )
    assert resp.status_code == 200


def test_bulk_delete_member_forbidden(client, member_headers, member_user, a_contact):
    resp = client.post(
        "/api/v1/contacts/bulk-delete",
        json={"ids": [a_contact["id"]]},
        headers=member_headers,
    )
    assert resp.status_code == 403


def test_bulk_delete_unauthenticated(client, a_contact):
    resp = client.post(
        "/api/v1/contacts/bulk-delete",
        json={"ids": [a_contact["id"]]},
    )
    assert resp.status_code == 401


# ── 5. DELETE /api/v1/lists/{id} ─────────────────────────────────────────

def test_delete_list_admin_success(client, auth_headers, admin_user, a_list):
    resp = client.delete(f"/api/v1/lists/{a_list.id}", headers=auth_headers)
    assert resp.status_code == 204


def test_delete_list_member_forbidden(client, member_headers, member_user, a_list):
    resp = client.delete(f"/api/v1/lists/{a_list.id}", headers=member_headers)
    assert resp.status_code == 403


def test_delete_list_unauthenticated(client, a_list):
    resp = client.delete(f"/api/v1/lists/{a_list.id}")
    assert resp.status_code == 401


# ── 6. POST /api/v1/invites/ ─────────────────────────────────────────────

def test_create_invite_admin_success(client, auth_headers, admin_user):
    resp = client.post(
        "/api/v1/invites/",
        json={"email": _unique_email("invite")},
        headers=auth_headers,
    )
    assert resp.status_code == 200


def test_create_invite_member_forbidden(client, member_headers, member_user):
    resp = client.post(
        "/api/v1/invites/",
        json={"email": _unique_email("invite")},
        headers=member_headers,
    )
    assert resp.status_code == 403


def test_create_invite_unauthenticated(client):
    resp = client.post(
        "/api/v1/invites/",
        json={"email": _unique_email("invite")},
    )
    assert resp.status_code == 401


# ── 7. GET /api/v1/invites/ ──────────────────────────────────────────────

def test_list_invites_admin_success(client, auth_headers, admin_user):
    resp = client.get("/api/v1/invites/", headers=auth_headers)
    assert resp.status_code == 200


def test_list_invites_member_forbidden(client, member_headers, member_user):
    resp = client.get("/api/v1/invites/", headers=member_headers)
    assert resp.status_code == 403


def test_list_invites_unauthenticated(client):
    resp = client.get("/api/v1/invites/")
    assert resp.status_code == 401


# ── 8. POST /api/v1/contacts/{id}/dnc ────────────────────────────────────

def test_set_dnc_admin_success(client, auth_headers, admin_user, a_contact):
    resp = client.post(
        f"/api/v1/contacts/{a_contact['id']}/dnc",
        json={"reason": "RBAC test"},
        headers=auth_headers,
    )
    assert resp.status_code == 200


def test_set_dnc_member_forbidden(client, member_headers, member_user, a_contact):
    resp = client.post(
        f"/api/v1/contacts/{a_contact['id']}/dnc",
        json={"reason": "RBAC test"},
        headers=member_headers,
    )
    assert resp.status_code == 403


def test_set_dnc_unauthenticated(client, a_contact):
    resp = client.post(
        f"/api/v1/contacts/{a_contact['id']}/dnc",
        json={"reason": "RBAC test"},
    )
    assert resp.status_code == 401


# ── 9. DELETE /api/v1/contacts/{id}/dnc ──────────────────────────────────

def test_clear_dnc_admin_success(client, auth_headers, admin_user, a_dnc_contact):
    resp = client.delete(
        f"/api/v1/contacts/{a_dnc_contact['id']}/dnc",
        headers=auth_headers,
    )
    assert resp.status_code == 204


def test_clear_dnc_member_forbidden(client, member_headers, member_user, a_dnc_contact):
    resp = client.delete(
        f"/api/v1/contacts/{a_dnc_contact['id']}/dnc",
        headers=member_headers,
    )
    assert resp.status_code == 403


def test_clear_dnc_unauthenticated(client, a_dnc_contact):
    resp = client.delete(f"/api/v1/contacts/{a_dnc_contact['id']}/dnc")
    assert resp.status_code == 401


# ── 10. POST /api/v1/campaigns ────────────────────────────────────────────

_CAMPAIGN_PAYLOAD = {
    "name": "RBAC Test Campaign",
    "subject": "Test Subject",
    "body_html": "<p>Hello</p>",
    "from_name": "Sarson Funds",
    "from_email": "noreply@sarsonfunds.com",
}


def test_create_campaign_admin_success(client, auth_headers, admin_user):
    payload = {**_CAMPAIGN_PAYLOAD, "name": f"RBAC Campaign {uuid.uuid4().hex[:6]}"}
    resp = client.post("/api/v1/campaigns", json=payload, headers=auth_headers)
    assert resp.status_code == 201


def test_create_campaign_member_forbidden(client, member_headers, member_user):
    payload = {**_CAMPAIGN_PAYLOAD, "name": f"RBAC Campaign {uuid.uuid4().hex[:6]}"}
    resp = client.post("/api/v1/campaigns", json=payload, headers=member_headers)
    assert resp.status_code == 403


def test_create_campaign_unauthenticated(client):
    payload = {**_CAMPAIGN_PAYLOAD, "name": f"RBAC Campaign {uuid.uuid4().hex[:6]}"}
    resp = client.post("/api/v1/campaigns", json=payload)
    assert resp.status_code == 401

"""Auth endpoint tests — login, registration, invite flow."""
import pytest


def test_login_success(client, admin_user):
    resp = client.post("/api/v1/auth/login", json={
        "email": "admin@sarsonfunds.com",
        "password": "Admin123!",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, admin_user):
    resp = client.post("/api/v1/auth/login", json={
        "email": "admin@sarsonfunds.com",
        "password": "wrong",
    })
    assert resp.status_code == 401


def test_login_nonexistent_user(client):
    resp = client.post("/api/v1/auth/login", json={
        "email": "nobody@example.com",
        "password": "whatever",
    })
    assert resp.status_code == 401


def test_me_requires_auth(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code in (401, 403)


def test_me_with_token(client, auth_headers):
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "admin@sarsonfunds.com"


def test_create_user_sarsonfunds_bypasses_invite(client, auth_headers):
    resp = client.post("/api/v1/users/", json={
        "email": "new@sarsonfunds.com",
        "name": "New User",
        "password": "NewUser123!",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "new@sarsonfunds.com"


def test_create_user_weak_password(client, auth_headers):
    resp = client.post("/api/v1/users/", json={
        "email": "weak@sarsonfunds.com",
        "name": "Weak",
        "password": "short",
    }, headers=auth_headers)
    assert resp.status_code == 422


def test_refresh_token(client, admin_user):
    login = client.post("/api/v1/auth/login", json={
        "email": "admin@sarsonfunds.com",
        "password": "Admin123!",
    })
    refresh = login.json()["refresh_token"]
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    assert "access_token" in resp.json()

"""Contact CRUD tests — create, read, search, soft delete, pagination."""
import pytest


def test_create_contact(client, auth_headers):
    resp = client.post("/api/v1/contacts", json={
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com",
    }, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["first_name"] == "John"
    assert data["email"] == "john@example.com"


def test_list_contacts_paginated(client, auth_headers):
    # Create a few contacts
    for i in range(3):
        client.post("/api/v1/contacts", json={
            "first_name": f"User{i}",
            "email": f"user{i}@example.com",
        }, headers=auth_headers)

    resp = client.get("/api/v1/contacts?per_page=2", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["per_page"] == 2
    assert data["total"] == 3
    assert len(data["data"]) == 2


def test_get_contact(client, auth_headers):
    create = client.post("/api/v1/contacts", json={
        "first_name": "Jane",
        "email": "jane@example.com",
    }, headers=auth_headers)
    contact_id = create.json()["id"]

    resp = client.get(f"/api/v1/contacts/{contact_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["first_name"] == "Jane"


def test_soft_delete_contact(client, auth_headers):
    create = client.post("/api/v1/contacts", json={
        "first_name": "Delete",
        "email": "delete@example.com",
    }, headers=auth_headers)
    contact_id = create.json()["id"]

    resp = client.delete(f"/api/v1/contacts/{contact_id}", headers=auth_headers)
    assert resp.status_code == 204

    # Should be gone from list
    resp = client.get(f"/api/v1/contacts/{contact_id}", headers=auth_headers)
    assert resp.status_code == 404


def test_duplicate_email_rejected(client, auth_headers):
    client.post("/api/v1/contacts", json={
        "first_name": "First",
        "email": "dup@example.com",
    }, headers=auth_headers)
    resp = client.post("/api/v1/contacts", json={
        "first_name": "Second",
        "email": "dup@example.com",
    }, headers=auth_headers)
    assert resp.status_code == 409


def test_search_contacts(client, auth_headers):
    client.post("/api/v1/contacts", json={
        "first_name": "Searchable",
        "last_name": "Person",
        "email": "searchable@example.com",
    }, headers=auth_headers)

    resp = client.get("/api/v1/contacts?search=Searchable", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

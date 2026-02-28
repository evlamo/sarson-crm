"""Import pipeline tests — placeholder for CSV import testing."""
import pytest


def test_health_endpoint(client):
    """Basic smoke test — health endpoint works."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# TODO: Add CSV import tests once test fixtures are prepared
# - Upload CSV, verify import job created
# - Verify contacts created from CSV rows
# - Verify dedup on email
# - Verify error handling for malformed CSV

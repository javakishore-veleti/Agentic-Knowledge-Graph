"""API tests against a real Postgres.

Skipped rather than mocked when no database is reachable: the things worth testing here
are the database's constraints and views, and a mock would assert only that the mock
works.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("sqlalchemy")

DB = os.environ.get("AKG_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DB, reason="AKG_DATABASE_URL not set")


@pytest.fixture(scope="module")
def client() -> TestClient:
    from data_catalog.app import app

    return TestClient(app)


@pytest.fixture
def a_mio(client: TestClient):
    """Create a MIO for the test and remove it afterwards.

    Earlier these tests relied on rows seeded outside the suite, so they passed or failed
    depending on what happened to be in the database.
    """
    r = client.post("/api/v1/mios", json={
        "domain_code": "biomedical", "code": "test-mio", "name": "Test MIO",
        "tech_stack": "csr_graph",
    })
    assert r.status_code == 201, r.text
    mio = r.json()["mio"]
    yield mio
    client.delete(f"/api/v1/mios/{mio['mio_id']}")


def test_health_reports_schema_presence(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["database"] is True
    assert body["catalog_schema"] is True
    # A non-zero drift count means wf_execs_json disagrees with wf_exec_log.
    assert body["drift"] == 0
    assert body["status"] == "ok"


def test_trace_id_is_echoed(client: TestClient) -> None:
    r = client.get("/health", headers={"x-trace-id": "trace-abc123"})
    assert r.headers["x-trace-id"] == "trace-abc123"


def test_trace_id_is_minted_when_absent(client: TestClient) -> None:
    r = client.get("/health")
    assert r.headers.get("x-trace-id")


def test_list_domains(client: TestClient) -> None:
    r = client.get("/api/v1/domains")
    assert r.status_code == 200
    assert r.json()["page"]["total"] >= 1


def test_mio_response_does_not_echo_the_tenant(client: TestClient) -> None:
    """A client already knows its tenant; echoing it is noise, and the view carries it."""
    r = client.get("/api/v1/mios")
    assert r.status_code == 200, r.text
    for item in r.json()["items"]:
        assert "tenant_id" not in item


def test_list_mios_uses_the_overview_view(client: TestClient, a_mio: dict) -> None:
    r = client.get("/api/v1/mios")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items, "expected at least the MIO this test created"
    m = items[0]
    # Fields only the view provides.
    for field in ("validations_pass", "dataset_count", "workflow_count", "has_cdc",
                  "generated_mio_count"):
        assert field in m


def test_app_endpoint_response_cannot_carry_a_credential(client: TestClient) -> None:
    """The contract, not just the data: no credential-shaped field exists."""
    from data_catalog.dtos.catalog_dtos import AppEndpointDto as AppEndpointOut

    forbidden = {"password", "pwd", "secret", "token", "api_key", "apikey",
                 "connection_string", "sas_token", "access_key"}
    assert not (set(AppEndpointOut.model_fields) & forbidden)

    r = client.get("/api/v1/app-endpoints")
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert not (set(item) & forbidden)
        assert not (set(item.get("options", {})) & forbidden)


def test_bad_cursor_is_a_400_not_a_silent_restart(client: TestClient) -> None:
    r = client.get("/api/v1/domains", params={"cursor": "not-a-cursor"})
    assert r.status_code == 400


def test_limit_is_clamped(client: TestClient) -> None:
    r = client.get("/api/v1/domains", params={"limit": 99999})
    assert r.status_code == 200
    assert r.json()["page"]["limit"] <= 200

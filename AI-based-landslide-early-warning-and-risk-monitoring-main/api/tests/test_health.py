"""Tests for the platform endpoints.

These run with no database, no Redis and no network, which is the point: the
service must report its own degradation accurately rather than crash or, worse,
claim to be ready when it is not.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import DEV_JWT_SECRET, NER_STATES, Settings
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_is_a_pure_liveness_probe(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_meta_reports_all_eight_states_and_the_region_bbox(client: TestClient) -> None:
    response = client.get("/api/v1/meta")
    assert response.status_code == 200
    body = response.json()

    assert len(body["states_covered"]) == 8
    assert set(body["states_covered"]) == set(NER_STATES)

    west, south, east, north = body["bbox"]
    assert (west, south, east, north) == (88.0, 21.5, 97.5, 29.6)
    assert west < east and south < north


def test_meta_always_carries_the_decision_support_disclaimer(client: TestClient) -> None:
    # This string is a safety commitment from docs/MODEL_CARD.md §1, so it is
    # asserted rather than left to drift.
    body = client.get("/api/v1/meta").json()
    assert "Geological Survey of India" in body["disclaimer"]
    assert "not a substitute" in body["disclaimer"].lower()


def test_readiness_reports_503_and_names_each_failing_component(client: TestClient) -> None:
    # No Postgres or Redis is running in the test environment. The correct
    # behaviour is an explicit not-ready answer that says which dependency is
    # missing, never a blanket 200.
    response = client.get("/api/v1/ready")
    assert response.status_code == 503

    body = response.json()
    assert body["ready"] is False

    names = {component["name"] for component in body["components"]}
    assert names == {"postgres", "redis"}
    for component in body["components"]:
        assert component["state"] in {"ok", "degraded", "unavailable", "not_configured"}
        assert component["detail"]


def test_unknown_route_returns_rfc7807_problem_details(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")

    body = response.json()
    assert body["status"] == 404
    assert body["instance"] == "/api/v1/does-not-exist"
    assert "title" in body and "type" in body


def test_production_refuses_to_start_with_the_development_signing_key() -> None:
    # A predictable JWT secret in a system that authorises evacuation alerts is
    # a security failure, so configuration must reject it outright.
    with pytest.raises(ValueError, match="development default"):
        Settings(environment="production", jwt_secret_key=DEV_JWT_SECRET)

    accepted = Settings(environment="production", jwt_secret_key="a-real-secret-from-the-vault")
    assert accepted.environment == "production"


def test_openapi_schema_is_3_1(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert schema["openapi"].startswith("3.1")

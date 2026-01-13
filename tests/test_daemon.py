import pytest
from fastapi.testclient import TestClient
from daemon.server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "uptime_seconds" in data


def test_query_endpoint_exists(client):
    response = client.post("/query", json={"sql": "SELECT 1"})
    assert response.status_code == 200
    # Will fail with "Not implemented yet" - that's expected

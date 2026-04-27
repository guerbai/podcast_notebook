from fastapi.testclient import TestClient

from backend.app import create_app


def test_app_starts_and_serves_healthcheck():
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True

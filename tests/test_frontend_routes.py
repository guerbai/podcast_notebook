from fastapi.testclient import TestClient

from backend.app import create_app


def test_frontend_page_is_served():
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert "Podcast Notebook" in response.text
    assert "Search podcasts" in response.text
    assert 'src="/static/assets/logo.svg"' in response.text
    assert 'data-role="toast-region"' in response.text
    assert 'data-role="confirm-modal"' in response.text
    assert 'data-role="summary-modal"' in response.text

from fastapi.testclient import TestClient

from backend.app import create_app


def test_frontend_page_is_served():
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert "播客工作台" in response.text
    assert "搜索播客" in response.text
    assert "最近 10 期" in response.text
    assert 'data-role="toast-region"' in response.text
    assert 'data-role="confirm-modal"' in response.text
    assert 'data-role="summary-modal"' in response.text

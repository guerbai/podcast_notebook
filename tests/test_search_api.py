from fastapi.testclient import TestClient

from backend.app import create_app


def test_search_endpoints_exist():
    client = TestClient(create_app())
    assert client.get("/api/search/podcasts", params={"q": "大内密谈"}).status_code == 200
    assert (
        client.get(
            "/api/search/episodes",
            params={"rss_url": "http://example.com/feed.xml", "q": "Codex"},
        ).status_code
        == 200
    )

from fastapi.testclient import TestClient

import backend.app as app_module
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


def test_episode_search_returns_lightweight_items(monkeypatch):
    def fake_fetch_episodes(rss_url, q):
        return [
            {
                "title": "巴菲特专题",
                "guid": "episode-1",
                "audio_url": "https://example.com/audio.mp3",
                "published": "2026-05-02",
                "shownotes": "<p>very long shownotes</p>",
                "summary": "# generated summary should not be here",
            }
        ]

    monkeypatch.setattr(app_module, "fetch_episodes", fake_fetch_episodes)
    client = TestClient(create_app())

    response = client.get(
        "/api/search/episodes",
        params={"rss_url": "https://example.com/feed.xml", "q": "巴菲特"},
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item == {
        "title": "巴菲特专题",
        "guid": "episode-1",
        "audio_url": "https://example.com/audio.mp3",
        "published": "2026-05-02",
    }


def test_episode_search_returns_audio_duration_when_available(monkeypatch):
    def fake_fetch_episodes(rss_url, q):
        return [
            {
                "title": "短节目",
                "guid": "episode-2",
                "audio_url": "https://example.com/short.mp3",
                "audio_duration_seconds": 185.0,
                "published": "2026-05-02",
                "shownotes": "<p>very long shownotes</p>",
            }
        ]

    monkeypatch.setattr(app_module, "fetch_episodes", fake_fetch_episodes)
    client = TestClient(create_app())

    response = client.get(
        "/api/search/episodes",
        params={"rss_url": "https://example.com/feed.xml", "q": "短"},
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["audio_duration_seconds"] == 185.0


def test_episode_search_respects_limit(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "fetch_episodes",
        lambda rss_url, q: [
            {"title": "one", "guid": "1", "audio_url": "https://example.com/1.mp3", "published": ""},
            {"title": "two", "guid": "2", "audio_url": "https://example.com/2.mp3", "published": ""},
        ],
    )
    client = TestClient(create_app())

    response = client.get(
        "/api/search/episodes",
        params={"rss_url": "https://example.com/feed.xml", "limit": "1"},
    )

    assert response.status_code == 200
    assert [item["title"] for item in response.json()["items"]] == ["one"]

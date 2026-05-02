from backend.rss import filter_episodes, normalize_episodes
from backend import rss


def test_filter_episodes_matches_episode_keyword():
    episodes = [
        {"title": "vol.1385 从小龙虾跑路到Codex", "audio_url": "https://example.com/a.mp3"},
        {"title": "vol.1384 别的话题", "audio_url": "https://example.com/b.mp3"},
    ]
    result = filter_episodes(episodes, "Codex")
    assert len(result) == 1
    assert result[0]["title"].startswith("vol.1385")


def test_filter_episodes_matches_title_only():
    episodes = [
        {
            "title": "vol.1385 别的话题",
            "shownotes": "这期 shownotes 提到了巴菲特",
            "audio_url": "https://example.com/a.mp3",
        },
        {
            "title": "vol.1384 巴菲特专题",
            "shownotes": "",
            "audio_url": "https://example.com/b.mp3",
        },
    ]

    result = filter_episodes(episodes, "巴菲特")

    assert len(result) == 1
    assert result[0]["title"] == "vol.1384 巴菲特专题"


def test_fetch_episodes_uses_browser_like_headers_for_rss_sources(monkeypatch):
    rss.clear_episode_cache()
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>商业就是这样</title>
        <item>
          <title>商业小样38 | 拿什么回馈你，我的股东</title>
          <description>股东价值</description>
          <enclosure url="https://example.com/audio.mp3" type="audio/mpeg" />
        </item>
      </channel>
    </rss>
    """
    seen_headers = []

    class FakeResponse:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, headers=None, **kwargs):
            seen_headers.append(headers or {})

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            return FakeResponse(xml)

    monkeypatch.setattr(rss.httpx, "Client", FakeClient)

    episodes = rss.fetch_episodes("http://www.ximalaya.com/album/46587439.xml", "拿什么回馈你")

    assert episodes
    assert episodes[0]["shownotes"] == "股东价值"
    headers = seen_headers[0]
    assert headers["User-Agent"] == "Mozilla/5.0"


def test_fetch_episodes_caches_rss_for_six_hours(monkeypatch):
    rss.clear_episode_cache()
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>巴菲特专题</title>
          <description>shownotes</description>
          <enclosure url="https://example.com/audio.mp3" type="audio/mpeg" />
        </item>
      </channel>
    </rss>
    """
    calls = []
    now = [1_000.0]

    class FakeResponse:
        text = xml

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            calls.append(url)
            return FakeResponse()

    monkeypatch.setattr(rss.httpx, "Client", FakeClient)
    monkeypatch.setattr(rss.time, "monotonic", lambda: now[0])

    assert rss.fetch_episodes("https://example.com/feed.xml", "巴菲特")
    assert rss.fetch_episodes("https://example.com/feed.xml", "巴菲特")
    now[0] += rss.EPISODE_CACHE_TTL_SECONDS + 1
    assert rss.fetch_episodes("https://example.com/feed.xml", "巴菲特")

    assert len(calls) == 2


def test_normalize_episodes_prefers_content_encoded_for_shownotes():
    episodes = normalize_episodes(
        [
            {
                "title": "Shownotes rich text",
                "id": "episode-1",
                "enclosures": [{"href": "https://example.com/audio.mp3"}],
                "summary": "short summary",
                "content": [{"value": "<p>full shownotes</p>"}],
            }
        ]
    )

    assert episodes[0]["shownotes"] == "<p>full shownotes</p>"

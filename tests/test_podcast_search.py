from backend.podcast_search import normalize_search_results


def test_normalize_search_results_keeps_title_and_rss():
    raw = [{"title": "大内密谈", "rss_url": "http://rss.example.com/feed.xml"}]
    result = normalize_search_results(raw)
    assert result[0]["title"] == "大内密谈"
    assert result[0]["rss_url"] == "http://rss.example.com/feed.xml"

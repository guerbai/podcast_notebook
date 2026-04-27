from __future__ import annotations

from typing import Any

import httpx


ITUNES_SEARCH_URL = "https://itunes.apple.com/search"


def normalize_search_results(raw_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for item in raw_results:
        title = item.get("title") or item.get("collectionName") or ""
        rss_url = item.get("rss_url") or item.get("feedUrl") or ""
        if not title or not rss_url:
            continue
        normalized.append(
            {
                "title": title,
                "author": item.get("artistName", ""),
                "rss_url": rss_url,
                "artwork_url": item.get("artworkUrl600") or item.get("artworkUrl100") or "",
            }
        )
    return normalized


def search_podcasts(query: str, limit: int = 10) -> list[dict[str, Any]]:
    if not query.strip():
        return []

    params = {
        "media": "podcast",
        "entity": "podcast",
        "term": query,
        "limit": limit,
    }
    with httpx.Client(timeout=15, follow_redirects=True) as client:
        response = client.get(ITUNES_SEARCH_URL, params=params)
        response.raise_for_status()
        payload = response.json()

    results = payload.get("results", [])
    return normalize_search_results(results)

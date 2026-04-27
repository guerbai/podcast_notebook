from __future__ import annotations

from typing import Any

import feedparser
import httpx


RSS_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _extract_audio_url(entry: dict[str, Any]) -> str:
    enclosures = entry.get("enclosures") or []
    for enclosure in enclosures:
        href = enclosure.get("href") or enclosure.get("url")
        if href:
            return href
    links = entry.get("links") or []
    for link in links:
        href = link.get("href")
        link_type = link.get("type", "")
        if href and "audio" in link_type:
            return href
    return ""


def _extract_shownotes(entry: dict[str, Any]) -> str:
    content_items = entry.get("content") or []
    for item in content_items:
        value = item.get("value", "").strip()
        if value:
            return value
    return (entry.get("summary", "") or entry.get("description", "")).strip()


def normalize_episodes(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    episodes = []
    for entry in entries:
        title = entry.get("title", "").strip()
        audio_url = _extract_audio_url(entry)
        if not title or not audio_url:
            continue
        episodes.append(
            {
                "title": title,
                "guid": entry.get("id") or entry.get("guid"),
                "audio_url": audio_url,
                "published": entry.get("published", ""),
                "summary": _extract_shownotes(entry),
            }
        )
    return episodes


def filter_episodes(episodes: list[dict[str, Any]], keyword: str) -> list[dict[str, Any]]:
    needle = keyword.strip().lower()
    if not needle:
        return episodes

    matched = []
    for episode in episodes:
        haystacks = [
            episode.get("title", "").lower(),
            episode.get("summary", "").lower(),
        ]
        if any(needle in haystack for haystack in haystacks):
            matched.append(episode)
    return matched


def fetch_episodes(rss_url: str, keyword: str = "") -> list[dict[str, Any]]:
    if not rss_url.strip():
        return []

    try:
        with httpx.Client(
            timeout=20,
            follow_redirects=True,
            headers=RSS_REQUEST_HEADERS,
        ) as client:
            response = client.get(rss_url)
            response.raise_for_status()
    except httpx.HTTPError:
        return []

    parsed = feedparser.parse(response.text)
    episodes = normalize_episodes(parsed.entries)
    return filter_episodes(episodes, keyword)

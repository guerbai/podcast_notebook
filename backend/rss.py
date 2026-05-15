from __future__ import annotations

import time
from typing import Any

import feedparser
import httpx


RSS_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

EPISODE_CACHE_TTL_SECONDS = 6 * 60 * 60
_EPISODE_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}


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


def _parse_duration_seconds(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if value >= 0 else None

    text = str(value).strip()
    if not text:
        return None
    try:
        if ":" not in text:
            seconds = float(text)
            return seconds if seconds >= 0 else None

        total = 0.0
        for part in text.split(":"):
            if not part:
                return None
            number = float(part)
            if number < 0:
                return None
            total = total * 60 + number
        return total
    except ValueError:
        return None


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
                "published_parsed": entry.get("published_parsed"),
                "shownotes": _extract_shownotes(entry),
                "audio_duration_seconds": _parse_duration_seconds(entry.get("itunes_duration")),
            }
        )
    return episodes


def filter_episodes(episodes: list[dict[str, Any]], keyword: str) -> list[dict[str, Any]]:
    needle = keyword.strip().lower()
    if not needle:
        return episodes

    matched = []
    for episode in episodes:
        if needle in episode.get("title", "").lower():
            matched.append(episode)
    return matched


def clear_episode_cache() -> None:
    _EPISODE_CACHE.clear()


def _copy_episodes(episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(episode) for episode in episodes]


def _cached_episodes(rss_url: str) -> list[dict[str, Any]] | None:
    cached = _EPISODE_CACHE.get(rss_url)
    if cached is None:
        return None
    cached_at, episodes = cached
    if time.monotonic() - cached_at > EPISODE_CACHE_TTL_SECONDS:
        _EPISODE_CACHE.pop(rss_url, None)
        return None
    return _copy_episodes(episodes)


def _fetch_all_episodes(rss_url: str, *, raise_on_error: bool = False) -> list[dict[str, Any]]:
    cached = _cached_episodes(rss_url)
    if cached is not None:
        return cached

    try:
        with httpx.Client(
            timeout=20,
            follow_redirects=True,
            headers=RSS_REQUEST_HEADERS,
        ) as client:
            response = client.get(rss_url)
            response.raise_for_status()
    except httpx.HTTPError:
        if raise_on_error:
            raise
        return []

    parsed = feedparser.parse(response.text)
    episodes = normalize_episodes(parsed.entries)
    _EPISODE_CACHE[rss_url] = (time.monotonic(), _copy_episodes(episodes))
    return episodes


def fetch_episodes(rss_url: str, keyword: str = "") -> list[dict[str, Any]]:
    if not rss_url.strip():
        return []
    episodes = _fetch_all_episodes(rss_url)
    return filter_episodes(episodes, keyword)


def fetch_episodes_strict(rss_url: str, keyword: str = "") -> list[dict[str, Any]]:
    if not rss_url.strip():
        return []
    episodes = _fetch_all_episodes(rss_url, raise_on_error=True)
    return filter_episodes(episodes, keyword)

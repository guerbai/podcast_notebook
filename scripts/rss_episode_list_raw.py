from __future__ import annotations

import json
import sys

import feedparser
import httpx


RSS_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def extract_audio_url(entry) -> str:
    for enclosure in entry.get("enclosures") or []:
        href = enclosure.get("href") or enclosure.get("url")
        if href:
            return href
    for link in entry.get("links") or []:
        href = link.get("href")
        link_type = link.get("type", "")
        if href and "audio" in link_type:
            return href
    return ""


def main() -> None:
    rss_url = " ".join(sys.argv[1:]).strip()
    if not rss_url:
        raise SystemExit("Usage: python scripts/rss_episode_list_raw.py <feedUrl>")

    response = httpx.get(
        rss_url,
        headers=RSS_REQUEST_HEADERS,
        timeout=20,
        follow_redirects=True,
    )
    response.raise_for_status()

    parsed = feedparser.parse(response.text)
    episodes = []
    for entry in parsed.entries:
        episodes.append(
            {
                "title": entry.get("title", ""),
                "published": entry.get("published", ""),
                "guid": entry.get("id") or entry.get("guid", ""),
                "audio_url": extract_audio_url(entry),
            }
        )

    print(json.dumps({"feed": parsed.feed, "episodes": episodes}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

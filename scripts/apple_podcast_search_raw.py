from __future__ import annotations

import json
import sys

import httpx


ITUNES_SEARCH_URL = "https://itunes.apple.com/search"


def main() -> None:
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        raise SystemExit("Usage: python scripts/apple_podcast_search_raw.py <keyword>")

    response = httpx.get(
        ITUNES_SEARCH_URL,
        params={
            "media": "podcast",
            "entity": "podcast",
            "term": query,
            "limit": 10,
        },
        timeout=15,
        follow_redirects=True,
    )
    response.raise_for_status()
    print(json.dumps(response.json(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

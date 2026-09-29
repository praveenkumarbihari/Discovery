from __future__ import annotations

import httpx

from .relevance import is_relevant, normalize_text

HN_SEARCH = "https://hn.algolia.com/api/v1/search"


def fetch_hn_discussions(query: str, *, limit: int = 10) -> list[dict]:
    # Require phrase match in Algolia when possible
    params = {
        "query": f'"Google Photos" {query} search find',
        "tags": "(story,comment)",
        "hitsPerPage": min(max(limit * 4, 20), 50),
    }
    headers = {"User-Agent": "DiscoveryEngine/1.0"}

    with httpx.Client(headers=headers, timeout=30.0) as client:
        response = client.get(HN_SEARCH, params=params)
        response.raise_for_status()
        hits = response.json().get("hits") or []

    results: list[dict] = []
    seen: set[str] = set()
    for hit in hits:
        text = normalize_text(
            hit.get("comment_text") or hit.get("story_text") or hit.get("title") or ""
        )
        if not is_relevant(text, query):
            continue
        object_id = str(hit.get("objectID") or hit.get("story_id") or len(results))
        if object_id in seen:
            continue
        seen.add(object_id)

        story_id = hit.get("story_id") or hit.get("parent_id") or object_id
        url = f"https://news.ycombinator.com/item?id={story_id}"
        results.append(
            {
                "id": f"hn_{object_id}",
                "source": "Hacker News",
                "raw_text": text[:8000],
                "url": url,
                "discovered_from": "hackernews",
            }
        )
        if len(results) >= limit:
            break

    return results

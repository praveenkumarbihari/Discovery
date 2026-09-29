from __future__ import annotations

import time
from typing import Any

import httpx

USER_AGENT = "Mozilla/5.0 (compatible; DiscoveryEngine/1.0; +https://localhost)"
DEFAULT_SUBREDDITS = ("googlephotos", "GooglePixel", "android", "ios")
PULLPUSH = "https://api.pullpush.io/reddit/search/submission/"


def fetch_reddit_posts(
    query: str,
    *,
    limit_per_sub: int = 5,
    subreddits: tuple[str, ...] = DEFAULT_SUBREDDITS,
) -> list[dict]:
    """Best-effort Reddit discovery via PullPush archive API."""
    headers = {"User-Agent": USER_AGENT}
    results: list[dict] = []
    seen_ids: set[str] = set()

    with httpx.Client(headers=headers, timeout=45.0, follow_redirects=True) as client:
        for subreddit in subreddits:
            if len(results) >= limit_per_sub * len(subreddits):
                break
            children = _pullpush_search(
                client,
                {"q": query, "subreddit": subreddit, "size": min(limit_per_sub, 25)},
            )
            for data in children:
                entry = _submission_to_entry(data, subreddit)
                if entry and entry["id"] not in seen_ids:
                    seen_ids.add(entry["id"])
                    results.append(entry)
            time.sleep(1.2)

        if len(results) < limit_per_sub:
            children = _pullpush_search(
                client,
                {"q": f"google photos {query}", "size": min(20, limit_per_sub * 3)},
            )
            for data in children:
                sub = (data.get("subreddit") or "").lower()
                if sub and "photo" not in sub and "google" not in sub and "android" not in sub:
                    continue
                entry = _submission_to_entry(data, sub or "reddit")
                if entry and entry["id"] not in seen_ids:
                    seen_ids.add(entry["id"])
                    results.append(entry)

    if not results:
        raise RuntimeError(
            "Reddit is rate-limited or blocked from this network. "
            "Use Stack Exchange / Hacker News sources or try again later."
        )
    return results


def _pullpush_search(client: httpx.Client, params: dict[str, Any]) -> list[dict]:
    response = client.get(PULLPUSH, params=params)
    if response.status_code == 429:
        time.sleep(2.5)
        response = client.get(PULLPUSH, params=params)
    if response.status_code >= 400:
        raise RuntimeError(f"PullPush HTTP {response.status_code}")
    payload = response.json()
    if isinstance(payload, dict) and payload.get("data"):
        return payload["data"]
    if isinstance(payload, list):
        return payload
    return []


def _submission_to_entry(data: dict, subreddit: str) -> dict | None:
    post_id = data.get("id") or data.get("name")
    if not post_id:
        return None
    title = (data.get("title") or "").strip()
    body = (data.get("selftext") or data.get("body") or "").strip()
    if body in ("[removed]", "[deleted]"):
        body = ""
    text = body or title
    if len(text) < 25:
        return None
    if title and body and title not in body:
        text = f"{title}\n\n{body}"
    permalink = data.get("permalink") or ""
    if permalink and not permalink.startswith("http"):
        url = f"https://www.reddit.com{permalink}"
    else:
        url = permalink or None
    sub = data.get("subreddit") or subreddit
    return {
        "id": f"reddit_{post_id}",
        "source": f"Reddit (r/{sub})",
        "raw_text": text[:8000],
        "url": url,
        "discovered_from": "reddit",
    }

from __future__ import annotations

import time

import httpx

from ..models import RawItem
from ..utils import author_hash, stable_id, utcnow
from .base import Collector

USER_AGENT = "DiscoveryEngine/1.0 (assignment; contact local)"


class RedditCollector(Collector):
    name = "reddit"

    def __init__(
        self,
        subreddits: list[str],
        search_queries: list[str],
        delay_seconds: float = 2.0,
        limit_per_query: int = 100,
        pages_per_query: int = 3,
    ):
        self.subreddits = subreddits
        self.search_queries = search_queries
        self.delay_seconds = delay_seconds
        self.limit_per_query = min(max(limit_per_query, 1), 100)
        self.pages_per_query = max(pages_per_query, 1)

    def collect(self) -> list[RawItem]:
        items: list[RawItem] = []
        seen: set[str] = set()
        headers = {"User-Agent": USER_AGENT}

        with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
            for subreddit in self.subreddits:
                for query in self.search_queries:
                    after: str | None = None
                    for _page in range(self.pages_per_query):
                        url = f"https://www.reddit.com/r/{subreddit}/search.json"
                        params: dict[str, str | int] = {
                            "q": query,
                            "restrict_sr": "on",
                            "sort": "relevance",
                            "limit": self.limit_per_query,
                        }
                        if after:
                            params["after"] = after
                        try:
                            resp = client.get(url, params=params)
                            if resp.status_code >= 400:
                                break
                            payload = resp.json()
                            children = payload.get("data", {}).get("children", [])
                            after = payload.get("data", {}).get("after")
                        except Exception:
                            break

                        if not children:
                            break

                        for child in children:
                            data = child.get("data") or {}
                            sid = data.get("id")
                            if not sid or sid in seen:
                                continue
                            title = (data.get("title") or "").strip()
                            body = (data.get("selftext") or "").strip()
                            text = body or title
                            if subreddit.lower() == "tipofmytongue":
                                blob = f"{title} {body}".lower()
                                if not any(
                                    k in blob
                                    for k in (
                                        "photo",
                                        "picture",
                                        "screenshot",
                                        "google photos",
                                    )
                                ):
                                    continue
                            if len(text) < 20:
                                continue
                            seen.add(sid)
                            permalink = data.get("permalink") or ""
                            items.append(
                                RawItem(
                                    id=stable_id("reddit", sid),
                                    source="reddit",
                                    source_id=sid,
                                    url=f"https://www.reddit.com{permalink}"
                                    if permalink
                                    else None,
                                    author_hash=author_hash(data.get("author")),
                                    created_at=None,
                                    rating=None,
                                    title=title or None,
                                    text=text if not body else f"{title}\n\n{body}".strip(),
                                    parent_context=None,
                                    country=None,
                                    lang="en",
                                    collected_at=utcnow(),
                                )
                            )

                        time.sleep(self.delay_seconds)
                        if not after:
                            break
        return items

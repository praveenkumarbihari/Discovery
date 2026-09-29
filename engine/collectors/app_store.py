from __future__ import annotations

import httpx

from ..models import RawItem
from ..utils import author_hash, stable_id, utcnow
from .base import Collector


class AppStoreCollector(Collector):
    name = "app_store"

    def __init__(self, app_id: str, countries: list[str], max_pages: int = 10):
        self.app_id = app_id
        self.countries = countries
        self.max_pages = max_pages

    def collect(self) -> list[RawItem]:
        items: list[RawItem] = []
        seen: set[str] = set()
        headers = {"User-Agent": "DiscoveryEngine/1.0 (assignment research)"}

        with httpx.Client(timeout=30.0, headers=headers, follow_redirects=True) as client:
            for country in self.countries:
                for page in range(1, self.max_pages + 1):
                    url = (
                        f"https://itunes.apple.com/{country}/rss/customerreviews/"
                        f"page={page}/id={self.app_id}/sortby=mostrecent/json"
                    )
                    try:
                        resp = client.get(url)
                        if resp.status_code != 200:
                            break
                        data = resp.json()
                    except Exception:
                        break

                    entries = (
                        data.get("feed", {}).get("entry")
                        or data.get("feed", {}).get("entries")
                        or []
                    )
                    if isinstance(entries, dict):
                        entries = [entries]
                    if not entries:
                        break

                    for entry in entries:
                        if not isinstance(entry, dict):
                            continue
                        if entry.get("im:rating") is None and "content" not in entry:
                            continue
                        sid = str(entry.get("id", {}).get("label") or entry.get("id") or len(items))
                        if sid in seen:
                            continue
                        seen.add(sid)
                        text = (
                            entry.get("content", {}).get("label")
                            if isinstance(entry.get("content"), dict)
                            else entry.get("content")
                        ) or ""
                        text = str(text).strip()
                        if not text:
                            continue
                        rating_raw = entry.get("im:rating", {}).get("label")
                        items.append(
                            RawItem(
                                id=stable_id("app_store", f"{country}:{sid}"),
                                source="app_store",
                                source_id=sid,
                                url=entry.get("link", {}).get("attributes", {}).get("href")
                                if isinstance(entry.get("link"), dict)
                                else None,
                                author_hash=author_hash(
                                    entry.get("author", {}).get("name", {}).get("label")
                                    if isinstance(entry.get("author"), dict)
                                    else None
                                ),
                                created_at=None,
                                rating=int(rating_raw) if rating_raw and str(rating_raw).isdigit() else None,
                                title=entry.get("title", {}).get("label")
                                if isinstance(entry.get("title"), dict)
                                else None,
                                text=text,
                                country=country,
                                lang="en",
                                collected_at=utcnow(),
                            )
                        )
        return items

from __future__ import annotations

from google_play_scraper import Sort, reviews

from ..models import RawItem
from ..utils import author_hash, stable_id, utcnow
from .base import Collector

_SORT_BY_NAME = {
    "newest": Sort.NEWEST,
    "relevant": Sort.MOST_RELEVANT,
    "rating": Sort.RATING,
}


class PlayStoreCollector(Collector):
    name = "play_store"

    def __init__(
        self,
        app_id: str,
        countries: list[str],
        per_sort_limit: int = 500,
        sorts: list[str] | None = None,
    ):
        self.app_id = app_id
        self.countries = countries
        self.per_sort_limit = per_sort_limit
        self.sorts = sorts or ["newest", "relevant"]

    def collect(self) -> list[RawItem]:
        items: list[RawItem] = []
        seen: set[str] = set()
        sort_enums = [_SORT_BY_NAME[s] for s in self.sorts if s in _SORT_BY_NAME]
        if not sort_enums:
            sort_enums = [Sort.NEWEST, Sort.MOST_RELEVANT]

        for country in self.countries:
            for sort in sort_enums:
                continuation_token = None
                fetched_api_rows = 0
                stale_pages = 0
                while fetched_api_rows < self.per_sort_limit:
                    page_size = min(200, self.per_sort_limit - fetched_api_rows)
                    batch, continuation_token = reviews(
                        self.app_id,
                        lang="en",
                        country=country,
                        sort=sort,
                        count=page_size,
                        continuation_token=continuation_token,
                    )
                    if not batch:
                        break
                    before = len(items)
                    for row in batch:
                        sid = str(row.get("reviewId") or len(items))
                        if sid in seen:
                            continue
                        seen.add(sid)
                        text = (row.get("content") or "").strip()
                        if not text:
                            continue
                        items.append(
                            RawItem(
                                id=stable_id("play_store", f"{country}:{sid}"),
                                source="play_store",
                                source_id=sid,
                                url=f"https://play.google.com/store/apps/details?id={self.app_id}",
                                author_hash=author_hash(row.get("userName")),
                                created_at=row.get("at"),
                                rating=row.get("score"),
                                title=None,
                                text=text,
                                country=country,
                                lang="en",
                                collected_at=utcnow(),
                            )
                        )
                    fetched_api_rows += len(batch)
                    if len(items) == before:
                        stale_pages += 1
                        if stale_pages >= 2:
                            break
                    else:
                        stale_pages = 0
                    if not continuation_token:
                        break
        return items

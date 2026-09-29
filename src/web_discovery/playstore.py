from __future__ import annotations

import re

from .relevance import is_relevant_play_review, normalize_text


def fetch_play_reviews(query: str, *, limit: int = 10) -> list[dict]:
    """Fetch Google Photos Play Store reviews about search/find issues."""
    try:
        from google_play_scraper import Sort, reviews
    except ImportError as exc:
        raise RuntimeError("google-play-scraper is not installed.") from exc

    batch, _ = reviews(
        "com.google.android.apps.photos",
        lang="en",
        country="us",
        sort=Sort.NEWEST,
        count=min(400, limit * 50),
    )

    results: list[dict] = []
    for item in batch:
        content = normalize_text(item.get("content") or "")
        if not is_relevant_play_review(content, query):
            continue
        review_id = item.get("reviewId") or str(len(results))
        results.append(
            {
                "id": f"playstore_{review_id}",
                "source": "Google Play Store",
                "raw_text": content[:8000],
                "url": "https://play.google.com/store/apps/details?id=com.google.android.apps.photos",
                "discovered_from": "playstore",
            }
        )
        if len(results) >= limit:
            break

    return results


def _keyword_set(query: str) -> set[str]:
    base = {"search", "find", "photo", "album", "face", "ocr", "text", "locate", "filter"}
    for token in re.findall(r"[a-z0-9]+", query.lower()):
        if len(token) > 2:
            base.add(token)
    return base

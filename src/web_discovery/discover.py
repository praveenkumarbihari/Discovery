from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ..discovery_engine import ROOT
from .hackernews import fetch_hn_discussions
from .playstore import fetch_play_reviews
from .reddit import fetch_reddit_posts
from .relevance import filter_and_rank
from .stackexchange import fetch_stackexchange_posts

SourceName = Literal["reddit", "hackernews", "playstore", "stackexchange"]
CACHE_PATH = ROOT / "data" / "cache" / "last_discovery.json"

DEFAULT_QUERY = "google photos search can't find"


class DiscoverRequest(BaseModel):
    query: str = Field(default=DEFAULT_QUERY, min_length=3, max_length=200)
    limit: int = Field(default=24, ge=1, le=50)
    sources: list[SourceName] = Field(
        default_factory=lambda: ["stackexchange", "hackernews", "playstore", "reddit"]
    )


def _text_fingerprint(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _dedupe(entries: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for entry in entries:
        fp = _text_fingerprint(entry["raw_text"])
        if fp in seen:
            continue
        seen.add(fp)
        unique.append(entry)
    return unique


def discover_feedback(body: DiscoverRequest) -> dict:
    collected: list[dict] = []
    errors: list[str] = []
    n_src = max(len(body.sources), 1)
    per_source_limit = max(12, (body.limit * 2) // n_src + 10)

    for source in body.sources:
        try:
            if source == "reddit":
                collected.extend(
                    fetch_reddit_posts(body.query, limit_per_sub=max(3, per_source_limit // 2))
                )
            elif source == "hackernews":
                collected.extend(fetch_hn_discussions(body.query, limit=per_source_limit))
            elif source == "playstore":
                collected.extend(fetch_play_reviews(body.query, limit=per_source_limit))
            elif source == "stackexchange":
                collected.extend(fetch_stackexchange_posts(body.query, limit=per_source_limit))
        except Exception as exc:
            errors.append(f"{source}: {exc}")

    entries = _dedupe(collected)
    before_relevance = len(entries)
    entries = filter_and_rank(entries, body.query, min_score=14)
    entries = entries[: body.limit]

    if not entries and errors:
        raise RuntimeError("Discovery failed. " + " | ".join(errors))
    if not entries:
        raise RuntimeError(
            "No relevant Google Photos search discussions matched your query. "
            "Try: can't find old photo, search broken, filter by date, face search wrong."
        )

    filtered_out = before_relevance - len(entries)
    if filtered_out > 0:
        errors.append(f"relevance: removed {filtered_out} off-topic result(s)")

    payload = {
        "query": body.query,
        "discovered_at": datetime.now(UTC).isoformat(),
        "count": len(entries),
        "entries": [
            {
                "id": e["id"],
                "source": e["source"],
                "raw_text": e["raw_text"],
                "url": e.get("url"),
            }
            for e in entries
        ],
        "sources_used": body.sources,
        "warnings": errors,
    }
    if _disk_cache_enabled():
        _write_cache(payload)
    return payload


def _disk_cache_enabled() -> bool:
    return os.environ.get("DISCOVERY_DISK_CACHE", "").strip().lower() in ("1", "true", "yes")


def _write_cache(payload: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CACHE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def load_cached_discovery() -> dict | None:
    if not _disk_cache_enabled():
        return None
    if not CACHE_PATH.is_file():
        return None
    with CACHE_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)

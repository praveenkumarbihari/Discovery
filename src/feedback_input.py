"""Convert user-facing feedback forms into engine post records (server-side only)."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

SOURCE_PRESETS = (
    "Reddit (r/googlephotos)",
    "Google Play Store",
    "Apple App Store",
    "Google Support Community",
    "YouTube comments",
    "Other",
)


class FeedbackEntry(BaseModel):
    """Public input shape — no prompts or taxonomy fields."""

    id: str | None = Field(default=None, max_length=64)
    source: Annotated[str, Field(min_length=1, max_length=200)]
    raw_text: Annotated[str, Field(min_length=10, max_length=8000)]

    @field_validator("source", "raw_text")
    @classmethod
    def strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty.")
        return value


class AnalyzeBody(BaseModel):
    entries: list[FeedbackEntry] = Field(..., min_length=1, max_length=50)
    dry_run: bool = False


def entries_to_posts(entries: list[FeedbackEntry]) -> list[dict]:
    posts: list[dict] = []
    for index, entry in enumerate(entries, start=1):
        post_id = entry.id.strip() if entry.id else f"feedback_{index:03d}"
        if not _valid_id(post_id):
            post_id = f"feedback_{index:03d}"
        posts.append(
            {
                "id": post_id,
                "source": entry.source,
                "raw_text": entry.raw_text,
            }
        )
    return posts


def posts_to_entries(posts: list[dict]) -> list[dict]:
    """Shape for the UI (sample loader). Omits internal prompt fields."""
    return [
        {
            "id": post["id"],
            "source": post["source"],
            "raw_text": post["raw_text"],
        }
        for post in posts
    ]


def _valid_id(value: str) -> bool:
    return bool(re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", value))

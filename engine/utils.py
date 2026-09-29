from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime


def stable_id(source: str, source_id: str) -> str:
    return hashlib.sha256(f"{source}:{source_id}".encode("utf-8")).hexdigest()[:20]


def author_hash(author: str | None) -> str | None:
    if not author:
        return None
    return hashlib.sha256(author.strip().lower().encode("utf-8")).hexdigest()


def utcnow() -> datetime:
    return datetime.now(UTC)


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text))

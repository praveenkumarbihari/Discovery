from __future__ import annotations

import hashlib
import re

from ..models import RawItem
from ..utils import word_count

EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE = re.compile(r"\+?\d[\d\s\-()]{7,}\d")
HANDLE = re.compile(r"@[\w]{2,}")


def scrub_pii(text: str) -> str:
    text = EMAIL.sub("[email]", text)
    text = PHONE.sub("[phone]", text)
    text = HANDLE.sub("[handle]", text)
    return text


def norm_hash(text: str) -> str:
    norm = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def dedupe_items(items: list[RawItem]) -> list[RawItem]:
    seen: set[str] = set()
    out: list[RawItem] = []
    for item in items:
        h = norm_hash(item.text)
        if h in seen:
            continue
        seen.add(h)
        out.append(item.model_copy(update={"text": scrub_pii(item.text)}))
    return out


def length_filter(items: list[RawItem], min_words: int = 15, strong_keywords: list[str] | None = None) -> list[RawItem]:
    strong_keywords = strong_keywords or []
    kept: list[RawItem] = []
    for item in items:
        if word_count(item.text) >= min_words:
            kept.append(item)
            continue
        if any(k.lower() in item.text.lower() for k in strong_keywords):
            kept.append(item)
    return kept

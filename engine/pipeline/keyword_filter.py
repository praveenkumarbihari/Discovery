from __future__ import annotations

import re

from ..models import RawItem


def keyword_pass(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(t.lower() in lower for t in terms)


def filter_by_keywords(items: list[RawItem], terms: list[str]) -> tuple[list[RawItem], float]:
    if not items:
        return [], 0.0
    kept = [i for i in items if keyword_pass(i.text, terms)]
    rate = len(kept) / len(items)
    return kept, rate

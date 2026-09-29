"""Relevance filtering for Google Photos *search/retrieval* feedback only."""

from __future__ import annotations

import html
import re

# Product mention (not generic "photos")
_GOOGLE_PHOTOS = re.compile(
    r"google\s+photos?|photos?\s*(app|application)\s*(by|from)?\s*google",
    re.I,
)

# Search / retrieval / findability intent
_RETRIEVAL = re.compile(
    r"\bsearch\b|\bfind\b|\blocate\b|\bfilter\b|\bfilters\b|can't find|cannot find|"
    r"couldn't find|can not find|wrong results|too many results|no results|"
    r"doesn't show|does not show|didn't find|face search|ocr|text in photo|"
    r"handwriting|album|date range|scroll|browse|index|retrieve|retriev",
    re.I,
)

# Off-topic domains/topics (reject unless clearly Google Photos search)
_BLOCKLIST = re.compile(
    r"inaturalist|citizen science|\bherping\b|\bbirding\b|scuba diving|"
    r"\bmtp\b|usb transfer|cutting and pasting.*android device|"
    r"move files from android|private.project|find mails|"
    r"\bgmail\b|\binbox\b|emails? larger than",
    re.I,
)

_STRUGGLE = re.compile(
    r"can't|cannot|couldn't|doesn't|does not|didn't|not working|broken|terrible|"
    r"useless|hard to|struggle|issue|problem|fail|wrong|missing|confus|"
    r"help|how do i find|how to find",
    re.I,
)


def normalize_text(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def relevance_score(text: str, user_query: str = "") -> int:
    """Higher = more on-topic. Zero = reject."""
    body = normalize_text(text)
    if len(body) < 25:
        return 0
    lower = body.lower()

    if _BLOCKLIST.search(lower):
        return 0

    product = bool(_GOOGLE_PHOTOS.search(lower))
    retrieval = bool(_RETRIEVAL.search(lower))
    struggle = bool(_STRUGGLE.search(lower))

    if not product:
        return 0
    if not retrieval:
        return 0

    score = 10
    if struggle:
        score += 8
    if re.search(r"google photos search|search.*google photos", lower):
        score += 6
    if re.search(r"find.*photo|photo.*find|find.*picture", lower):
        score += 4

    qtokens = [t for t in re.findall(r"[a-z0-9']+", user_query.lower()) if len(t) > 3]
    for token in qtokens:
        if token in lower:
            score += 2

    return score


def is_relevant(text: str, user_query: str = "") -> bool:
    return relevance_score(text, user_query) >= 12


def is_relevant_play_review(text: str, user_query: str = "") -> bool:
    """Play Store reviews are always for Google Photos — require search/find pain."""
    body = normalize_text(text)
    if len(body) < 25:
        return False
    lower = body.lower()
    if not _RETRIEVAL.search(lower):
        return False
    if not (_STRUGGLE.search(lower) or re.search(r"\bsearch\b.*\b(bad|slow|broken|work)", lower)):
        return False
    if _BLOCKLIST.search(lower):
        return False
    return relevance_score(f"Google Photos app. {body}", user_query) >= 10 or bool(
        _RETRIEVAL.search(lower) and _STRUGGLE.search(lower)
    )


def filter_and_rank(entries: list[dict], user_query: str, *, min_score: int = 12) -> list[dict]:
    scored: list[tuple[int, dict]] = []
    for entry in entries:
        source = entry.get("discovered_from") or ""
        text = entry.get("raw_text") or ""
        if source == "playstore":
            ok = is_relevant_play_review(text, user_query)
            score = relevance_score(f"Google Photos. {text}", user_query) if ok else 0
        else:
            score = relevance_score(text, user_query)
            ok = score >= min_score
        if ok:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in scored]

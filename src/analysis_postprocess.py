"""Normalize LLM analysis output and recompute aggregate metrics."""

from __future__ import annotations

import json
import re
from collections import Counter

from .research_questions import build_research_insights_fallback

REMEMBERED_CLUES = {
    "relative time",
    "color/visual motif",
    "emotion/context",
    "co-occurring event",
    "broad location",
}

FORGOTTEN_METADATA = {
    "exact date/year",
    "exact location tag/geotag",
    "exact OCR text/keyword",
    "album name/file name",
}

FAILURE_STAGES = (
    "Expression Failure",
    "Interpretation Failure",
    "Evaluation Failure",
    "Refinement Failure",
)

_CLUE_ALIASES = {
    "time": "relative time",
    "relative timing": "relative time",
    "location": "broad location",
    "place": "broad location",
    "color": "color/visual motif",
    "visual": "color/visual motif",
    "context": "emotion/context",
    "emotion": "emotion/context",
    "event": "co-occurring event",
}

_FORGOTTEN_ALIASES = {
    "date": "exact date/year",
    "year": "exact date/year",
    "exact date": "exact date/year",
    "date/year": "exact date/year",
    "timestamp": "exact date/year",
    "when": "exact date/year",
    "geotag": "exact location tag/geotag",
    "location tag": "exact location tag/geotag",
    "location metadata": "exact location tag/geotag",
    "gps": "exact location tag/geotag",
    "place tag": "exact location tag/geotag",
    "ocr": "exact OCR text/keyword",
    "keyword": "exact OCR text/keyword",
    "keywords": "exact OCR text/keyword",
    "text": "exact OCR text/keyword",
    "exact text": "exact OCR text/keyword",
    "handwriting": "exact OCR text/keyword",
    "label text": "exact OCR text/keyword",
    "file name": "album name/file name",
    "filename": "album name/file name",
    "album": "album name/file name",
    "album name": "album name/file name",
    "folder": "album name/file name",
}


def _coerce_tag_list(value) -> list[str]:
    """LLMs sometimes return a string, null, or wrong container for tag arrays."""
    if value is None:
        return []
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        if value.startswith("[") and value.endswith("]"):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except json.JSONDecodeError:
                pass
        return [part.strip() for part in re.split(r"[,;|]", value) if part.strip()]
    if isinstance(value, (list, tuple)):
        out: list[str] = []
        for item in value:
            if item is None:
                continue
            if isinstance(item, dict):
                for key in ("value", "metadata", "type", "name", "label"):
                    if key in item and item[key]:
                        out.append(str(item[key]).strip())
                        break
                else:
                    out.append(str(item).strip())
            else:
                text = str(item).strip()
                if text:
                    out.append(text)
        return out
    return [str(value).strip()] if str(value).strip() else []


def _insight_tag_field(insight: dict, *keys: str) -> list:
    for key in keys:
        if key in insight and insight[key] is not None:
            return _coerce_tag_list(insight[key])
    return []


def infer_forgotten_metadata(raw_text: str) -> list[str]:
    """Best-effort tags when the model leaves forgotten_metadata empty."""
    t = (raw_text or "").lower()
    if len(t) < 20:
        return []

    inferred: list[str] = []
    date_signals = (
        "don't know the date",
        "dont know the date",
        "without date",
        "no date",
        "couldn't filter",
        "couldnt filter",
        "filter by",
        "which year",
        "forgot when",
        "don't remember when",
        "years ago",
        "months ago",
        "old photo",
        "timeline",
        "when it was taken",
    )
    ocr_signals = (
        "handwriting",
        "handwritten",
        "ocr",
        "text on",
        "on the label",
        "brand name",
        "can't remember the name",
        "cant remember the name",
        "document",
        "receipt",
        "screenshot",
        "keyword",
        "words on",
    )
    location_signals = (
        "geotag",
        "location tag",
        "where it was",
        "which trip",
        "different trips",
        "goa cafe",
    )
    album_signals = ("album", "folder", "file name", "filename", "which album")

    if any(s in t for s in date_signals):
        inferred.append("exact date/year")
    if any(s in t for s in ocr_signals):
        inferred.append("exact OCR text/keyword")
    if any(s in t for s in location_signals):
        inferred.append("exact location tag/geotag")
    if any(s in t for s in album_signals):
        inferred.append("album name/file name")

    if not inferred and any(
        w in t for w in ("search", "find", "can't find", "cant find", "looking for")
    ):
        inferred.append("exact date/year")
    return inferred


def _canon(value: str, allowed: set[str], aliases: dict[str, str]) -> str | None:
    v = value.strip().lower()
    for item in allowed:
        if v == item.lower():
            return item
    if v in aliases:
        return aliases[v]
    for item in allowed:
        if item.lower() in v or v in item.lower():
            return item
    return None


def normalize_insight_fields(insight: dict) -> list[str]:
    """Normalize clue/metadata enums; return list of validation warnings."""
    warnings: list[str] = []
    clues: list[str] = []
    for raw in _insight_tag_field(
        insight, "remembered_clues", "rememberedClues", "remembered_clue"
    ):
        c = _canon(str(raw), REMEMBERED_CLUES, _CLUE_ALIASES)
        if c:
            if c not in clues:
                clues.append(c)
        else:
            warnings.append(f"Unknown remembered_clue '{raw}' for {insight.get('id')}")
    insight["remembered_clues"] = clues

    forgotten: list[str] = []
    for raw in _insight_tag_field(
        insight,
        "forgotten_metadata",
        "forgottenMetadata",
        "forgotten_meta",
        "missing_metadata",
    ):
        m = _canon(str(raw), FORGOTTEN_METADATA, _FORGOTTEN_ALIASES)
        if m:
            if m not in forgotten:
                forgotten.append(m)
        else:
            warnings.append(f"Unknown forgotten_metadata '{raw}' for {insight.get('id')}")

    if not forgotten:
        forgotten = infer_forgotten_metadata(str(insight.get("raw_text") or ""))
        if forgotten:
            warnings.append(
                f"Inferred forgotten_metadata for {insight.get('id')} from post text"
            )

    insight["forgotten_metadata"] = forgotten

    stage = insight.get("failure_stage")
    if stage not in FAILURE_STAGES:
        warnings.append(f"Invalid failure_stage '{stage}' for {insight.get('id')}")
    return warnings


def compute_summary_metrics(insights: list[dict]) -> dict:
    counts = {stage: 0 for stage in FAILURE_STAGES}
    clue_counter: Counter[str] = Counter()
    forgotten_counter: Counter[str] = Counter()

    for insight in insights:
        stage = insight.get("failure_stage")
        if stage in counts:
            counts[stage] += 1
        for c in insight.get("remembered_clues") or []:
            clue_counter[c] += 1
        for m in insight.get("forgotten_metadata") or []:
            forgotten_counter[m] += 1

    return {
        "failure_stage_counts": counts,
        "top_remembered_clues": [
            {"clue": k, "count": v}
            for k, v in clue_counter.most_common()
        ],
        "top_forgotten_metadata": [
            {"metadata": k, "count": v}
            for k, v in forgotten_counter.most_common()
        ],
    }


def align_payload_to_input(payload: dict, feedback_posts: list[dict]) -> tuple[dict, list[str]]:
    """Force verbatim id/source/raw_text from input and recompute summary metrics."""
    warnings: list[str] = []
    by_id = {i.get("id"): i for i in payload.get("insights") or [] if i.get("id")}

    aligned: list[dict] = []
    for post in feedback_posts:
        pid = post["id"]
        insight = by_id.get(pid)
        if insight is None:
            raise ValueError(f"Model output missing insight for post id '{pid}'.")
        insight = dict(insight)
        insight["id"] = pid
        insight["source"] = post["source"]
        insight["raw_text"] = post["raw_text"]
        warnings.extend(normalize_insight_fields(insight))
        aligned.append(insight)

    payload = dict(payload)
    payload["insights"] = aligned
    payload["total_analyzed"] = len(aligned)
    payload["summary_metrics"] = compute_summary_metrics(aligned)
    insights_list = payload.get("research_insights")
    if not isinstance(insights_list, list) or len(insights_list) < 3:
        payload["research_insights"] = build_research_insights_fallback(
            aligned, payload["summary_metrics"]
        )
    return payload, warnings

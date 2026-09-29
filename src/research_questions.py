"""Assignment research-question framework for Discovery Engine."""

from __future__ import annotations

from collections import Counter

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_CATALOG_PATH = ROOT / "data" / "research_questions.json"


def load_catalog() -> dict:
    with _CATALOG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def flatten_questions(catalog: dict | None = None) -> list[dict]:
    catalog = catalog or load_catalog()
    flat: list[dict] = []
    for category in catalog.get("categories", []):
        for q in category.get("questions", []):
            flat.append(
                {
                    **q,
                    "category_id": category.get("id"),
                    "category_title": category.get("title"),
                }
            )
    return flat


def prompt_block() -> str:
    catalog = load_catalog()
    lines = [
        catalog.get("purpose", ""),
        "",
        "After classifying each post, synthesize batch-level research_insights using this question framework.",
        "Only answer questions supported by evidence in the batch; cite supporting post ids.",
        "",
    ]
    for category in catalog.get("categories", []):
        lines.append(f"## {category.get('title')}")
        for q in category.get("questions", []):
            lines.append(f"- [{q['id']}] {q['question']}")
            lines.append(f"  Goal: {q.get('insight_goal', '')}")
        lines.append("")
    return "\n".join(lines)


def suggested_searches(limit: int = 14) -> list[str]:
    seen: list[str] = []
    for q in flatten_questions():
        for hint in q.get("example_search_queries") or []:
            if hint not in seen:
                seen.append(hint)
            if len(seen) >= limit:
                return seen
    return seen


def build_research_insights_fallback(insights: list[dict], summary: dict) -> list[dict]:
    """Rule-based synthesis when the model omits research_insights."""
    if not insights:
        return []

    by_type = Counter(i.get("target_photo_type") for i in insights)
    stages = summary.get("failure_stage_counts") or {}
    top_clues = summary.get("top_remembered_clues") or []
    top_forgotten = summary.get("top_forgotten_metadata") or []
    formulations = Counter(i.get("user_search_formulation") for i in insights if i.get("user_search_formulation"))

    def ids_for(predicate) -> list[str]:
        return [i["id"] for i in insights if predicate(i)]

    def top_stage() -> str:
        return max(stages.items(), key=lambda x: x[1])[0] if stages else "Interpretation Failure"

    findings: list[dict] = []

    type_line = ", ".join(f"{k} ({v})" for k, v in by_type.most_common(3))
    findings.append(
        {
            "question_id": "rq_old_photo_types",
            "question": "What kinds of old photos do users struggle to retrieve?",
            "finding": f"Users report retrieval pain across: {type_line}.",
            "supporting_ids": [i["id"] for i in insights],
            "confidence": "medium",
        }
    )

    if top_clues:
        clue_line = ", ".join(f"{c['clue']} ({c['count']})" for c in top_clues[:4])
        findings.append(
            {
                "question_id": "rq_remembered_cues",
                "question": "What information do people actually remember about a photo?",
                "finding": f"Most cited remembered cues: {clue_line}.",
                "supporting_ids": ids_for(lambda i: bool(i.get("remembered_clues"))),
                "confidence": "high" if top_clues[0]["count"] >= 2 else "medium",
            }
        )

    if top_forgotten:
        forgot_line = ", ".join(f"{m['metadata']} ({m['count']})" for m in top_forgotten[:4])
        findings.append(
            {
                "question_id": "rq_forgotten_metadata",
                "question": "What information have they forgotten (date, location tag, album, text on photo)?",
                "finding": f"Commonly forgotten metadata: {forgot_line}.",
                "supporting_ids": ids_for(lambda i: bool(i.get("forgotten_metadata"))),
                "confidence": "high" if top_forgotten[0]["count"] >= 2 else "medium",
            }
        )

    if formulations:
        form_line = "; ".join(f"{k}" for k, _ in formulations.most_common(3))
        findings.append(
            {
                "question_id": "rq_search_formulation",
                "question": "How do users formulate searches when their memory is incomplete?",
                "finding": f"Search strategies observed: {form_line}.",
                "supporting_ids": [i["id"] for i in insights],
                "confidence": "medium",
            }
        )

    stage = top_stage()
    findings.append(
        {
            "question_id": "rq_failure_stages",
            "question": "At which retrieval stage do failures cluster: expression, interpretation, evaluation, or refinement?",
            "finding": f"Largest failure cluster in this batch: {stage} ({stages.get(stage, 0)} of {len(insights)} posts).",
            "supporting_ids": ids_for(lambda i: i.get("failure_stage") == stage),
            "confidence": "high",
        }
    )

    interp_ids = ids_for(lambda i: i.get("failure_stage") == "Interpretation Failure")
    if interp_ids:
        findings.append(
            {
                "question_id": "rq_content_mismatch",
                "question": "When users search, does the app return the wrong type of content (e.g., food photos instead of documents)?",
                "finding": "Several posts describe the engine retrieving the wrong semantic content type or missing visible text (interpretation failures).",
                "supporting_ids": interp_ids,
                "confidence": "medium",
            }
        )

    refine_ids = ids_for(lambda i: i.get("failure_stage") == "Refinement Failure")
    if refine_ids:
        findings.append(
            {
                "question_id": "rq_refinement_stuck",
                "question": "Where do users get stuck narrowing results (time, trip, event filters)?",
                "finding": "Users retrieve broad result sets but cannot narrow by time, trip, or event without better refinement tools.",
                "supporting_ids": refine_ids,
                "confidence": "medium",
            }
        )

    opportunities = [i.get("opportunity_area") for i in insights if i.get("opportunity_area")]
    if opportunities:
        findings.append(
            {
                "question_id": "rq_product_opportunities",
                "question": "What repeated product opportunities could improve Google Photos search?",
                "finding": opportunities[0] if len(opportunities) == 1 else f"Recurring themes include: {opportunities[0]}",
                "supporting_ids": [i["id"] for i in insights[:3]],
                "confidence": "medium",
            }
        )

    return findings

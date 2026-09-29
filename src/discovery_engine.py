"""Google Photos Discovery Engine — prompt assembly, LLM analysis, schema validation."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import jsonschema
from jsonschema import Draft202012Validator

from .analysis_postprocess import align_payload_to_input, compute_summary_metrics
from .llm_providers import (
    LLMProviderError,
    active_provider_info,
    chat_completion,
    default_model,
    provider_chain,
)
from .research_questions import prompt_block as research_questions_prompt_block

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / "prompts"
SCHEMA_PATH = ROOT / "schema" / "analysis_output.schema.json"


def load_dotenv() -> None:
    """Load KEY=VALUE lines from project .env into os.environ (does not override existing)."""
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def build_user_prompt(feedback_posts: list[dict]) -> str:
    template = load_text(PROMPTS_DIR / "user_template.txt")
    rubric = load_text(PROMPTS_DIR / "classification_rubric.txt")
    input_json = json.dumps(feedback_posts, indent=2, ensure_ascii=False)
    return (
        template.replace("{{RUBRIC}}", rubric)
        .replace("{{RESEARCH_QUESTIONS}}", research_questions_prompt_block())
        .replace("{{INPUT_JSON}}", input_json)
        .replace("{{POST_COUNT}}", str(len(feedback_posts)))
    )


def build_messages(feedback_posts: list[dict]) -> list[dict]:
    return [
        {"role": "system", "content": load_text(PROMPTS_DIR / "system.txt")},
        {"role": "user", "content": build_user_prompt(feedback_posts)},
    ]


ANALYZE_CHUNK_SIZE = 4


def _analysis_max_tokens(post_count: int) -> int:
    override = int(os.environ.get("OPENROUTER_MAX_TOKENS", "0") or "0")
    if override > 0:
        return override
    return min(8192, max(3072, 900 + post_count * 520))


def extract_json_object(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        raise json.JSONDecodeError("Empty model response", text, 0)

    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        text = text[start : end + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        repaired = re.sub(r",\s*([}\]])", r"\1", text)
        return json.loads(repaired)


def validate_output(payload: dict) -> None:
    schema = load_json(SCHEMA_PATH)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        lines = [f"  - {e.message} (at {list(e.path)})" for e in errors]
        raise jsonschema.ValidationError("Output failed schema validation:\n" + "\n".join(lines))


def _default_model() -> str:
    return active_provider_info()["model"]


def _dry_run_payload(feedback_posts: list[dict]) -> dict:
    reference = load_json(ROOT / "data" / "sample_output.json")
    by_id = {i["id"]: i for i in reference.get("insights", [])}
    missing = [p["id"] for p in feedback_posts if p["id"] not in by_id]
    if missing:
        raise ValueError(
            "Dry run only includes reference insights for sample ids; missing: "
            + ", ".join(missing)
        )
    payload = dict(reference)
    payload["insights"] = [dict(by_id[p["id"]]) for p in feedback_posts]
    payload, _ = align_payload_to_input(payload, feedback_posts)
    validate_output(payload)
    return payload


def _analyze_with_provider(
    provider: str,
    feedback_posts: list[dict],
    *,
    model: str | None,
) -> dict:
    messages = build_messages(feedback_posts)
    last_error: Exception | None = None
    max_tokens = _analysis_max_tokens(len(feedback_posts))
    resolved_model = model or default_model(provider)

    for attempt in range(4):
        content, finish_reason = chat_completion(
            provider,
            messages=messages,
            max_tokens=max_tokens,
            model=resolved_model,
        )
        truncated = finish_reason == "length"

        try:
            payload = extract_json_object(content)
            validate_output(payload)
            payload, warnings = align_payload_to_input(payload, feedback_posts)
            validate_output(payload)
            if warnings and attempt < 3:
                messages = messages + [
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": (
                            "Fix the analysis. Issues: "
                            + "; ".join(warnings)
                            + ". Re-apply the rubric strictly, especially failure_stage."
                        ),
                    },
                ]
                continue
            return payload
        except (json.JSONDecodeError, jsonschema.ValidationError, ValueError) as exc:
            last_error = exc
            if truncated:
                max_tokens = min(8192, max_tokens + 2048)
            if attempt < 3:
                hint = (
                    "Response was truncated by token limit; return compact JSON."
                    if truncated
                    else f"Your JSON was invalid or incomplete: {exc}."
                )
                messages = messages + [
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": (
                            f"{hint} Return valid JSON only, one insight per input id, "
                            "no markdown fences, no trailing commas."
                        ),
                    },
                ]
                continue
            if isinstance(exc, json.JSONDecodeError):
                raise LLMProviderError(f"Malformed JSON from {provider}: {exc}") from exc
            raise

    if last_error:
        if isinstance(last_error, json.JSONDecodeError):
            raise LLMProviderError(f"Malformed JSON from {provider}: {last_error}") from last_error
        raise last_error
    raise RuntimeError("Analysis failed after retries.")


def analyze_with_llm(feedback_posts: list[dict], *, model: str | None = None) -> dict:
    chain = provider_chain()
    if not chain:
        raise RuntimeError(
            "No LLM API key configured. Set OPENROUTER_API_KEY and/or GEMINI_API_KEY in .env."
        )

    provider_errors: list[str] = []
    for provider in chain:
        try:
            return _analyze_with_provider(provider, feedback_posts, model=model)
        except LLMProviderError as exc:
            provider_errors.append(f"{provider}: {exc}")
            continue

    detail = "; ".join(provider_errors)
    raise RuntimeError(
        f"All LLM providers failed ({detail}). "
        "Check API keys/credits, try fewer rows, or set LLM_PRIMARY=gemini in .env."
    )


def _merge_chunk_payloads(parts: list[dict], feedback_posts: list[dict]) -> dict:
    insights: list[dict] = []
    research_insights: list | None = None
    for part in parts:
        insights.extend(part.get("insights") or [])
        ri = part.get("research_insights")
        if isinstance(ri, list) and len(ri) >= 3:
            research_insights = ri

    payload = {
        "total_analyzed": len(feedback_posts),
        "insights": insights,
        "summary_metrics": compute_summary_metrics(insights),
        "research_insights": research_insights or [],
    }
    payload, _ = align_payload_to_input(payload, feedback_posts)
    return payload


def analyze_posts(feedback_posts: list[dict], *, dry_run: bool = False) -> dict:
    if not isinstance(feedback_posts, list):
        raise ValueError("Input must be an array of feedback posts.")
    if not feedback_posts:
        raise ValueError("Input array must contain at least one feedback post.")

    for i, post in enumerate(feedback_posts):
        if not isinstance(post, dict):
            raise ValueError(f"Post at index {i} must be an object.")
        for key in ("id", "source", "raw_text"):
            if key not in post or not str(post[key]).strip():
                raise ValueError(f"Post at index {i} is missing required field '{key}'.")

    if dry_run:
        payload = _dry_run_payload(feedback_posts)
    elif len(feedback_posts) <= ANALYZE_CHUNK_SIZE:
        payload = analyze_with_llm(feedback_posts)
    else:
        parts: list[dict] = []
        for i in range(0, len(feedback_posts), ANALYZE_CHUNK_SIZE):
            chunk = feedback_posts[i : i + ANALYZE_CHUNK_SIZE]
            parts.append(analyze_with_llm(chunk))
        payload = _merge_chunk_payloads(parts, feedback_posts)

    validate_output(payload)
    if payload.get("total_analyzed") != len(feedback_posts):
        raise ValueError(
            f"total_analyzed ({payload.get('total_analyzed')}) "
            f"does not match input length ({len(feedback_posts)})."
        )
    return payload


def run(
    input_path: Path,
    *,
    dry_run: bool = False,
    output_path: Path | None = None,
) -> dict:
    feedback_posts = load_json(input_path)
    payload = analyze_posts(feedback_posts, dry_run=dry_run)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")

    return payload

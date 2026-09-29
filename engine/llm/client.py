"""Provider-agnostic LLM client with caching, retries, and cost estimates."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import diskcache
from tenacity import retry, stop_after_attempt, wait_exponential

ROOT = Path(__file__).resolve().parent.parent.parent


def _cache() -> diskcache.Cache:
    cache_dir = os.environ.get("LLM_CACHE_DIR", str(ROOT / "data" / "cache" / "llm"))
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    return diskcache.Cache(cache_dir)


def _provider() -> str:
    if os.environ.get("OPENROUTER_API_KEY"):
        return "openrouter"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        return "google"
    raise RuntimeError("No LLM API key configured (.env)")


def _openai_compatible_client():
    from openai import OpenAI

    if os.environ.get("OPENROUTER_API_KEY"):
        return OpenAI(
            api_key=os.environ["OPENROUTER_API_KEY"],
            base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        )
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def estimate_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    # Rough defaults for budgeting / manifest (override in production billing)
    cheap = ("mini", "haiku", "flash")
    if any(x in model.lower() for x in cheap):
        return (tokens_in * 0.15 + tokens_out * 0.6) / 1_000_000
    return (tokens_in * 2.5 + tokens_out * 10.0) / 1_000_000


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def chat_json(
    *,
    model: str,
    system: str,
    user: str,
    prompt_version: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    key = hashlib.sha256(f"{prompt_version}|{model}|{system}|{user}".encode()).hexdigest()
    cache = _cache()
    if key in cache:
        meta, payload = cache[key]
        return payload, meta

    provider = _provider()
    if provider in ("openrouter", "openai"):
        client = _openai_compatible_client()
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        usage = resp.usage
        tokens_in = usage.prompt_tokens if usage else 0
        tokens_out = usage.completion_tokens if usage else 0
    else:
        raise RuntimeError(f"Provider '{provider}' JSON chat not wired yet in Phase 1.")

    payload = json.loads(content)
    meta = {
        "model": model,
        "provider": provider,
        "prompt_version": prompt_version,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": estimate_cost_usd(model, tokens_in, tokens_out),
    }
    cache[key] = (meta, payload)
    return payload, meta

"""OpenRouter, Gemini, and OpenAI chat with automatic fallback."""

from __future__ import annotations

import os
from typing import Any

import httpx

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class LLMProviderError(Exception):
    """HTTP/auth/rate-limit failure — try the next provider."""


def _gemini_key() -> str | None:
    key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    return key or None


def provider_chain() -> list[str]:
    """Order of providers to try (primary first, then fallback)."""
    primary = (os.environ.get("LLM_PRIMARY") or "auto").strip().lower()
    has_or = bool((os.environ.get("OPENROUTER_API_KEY") or "").strip())
    has_gemini = bool(_gemini_key())
    has_openai = bool((os.environ.get("OPENAI_API_KEY") or "").strip())

    if primary == "gemini":
        order = ["gemini", "openrouter", "openai"]
    elif primary == "openrouter":
        order = ["openrouter", "gemini", "openai"]
    elif primary == "openai":
        order = ["openai", "openrouter", "gemini"]
    else:
        order = ["openrouter", "gemini", "openai"]

    chain: list[str] = []
    for name in order:
        if name == "openrouter" and has_or and name not in chain:
            chain.append(name)
        elif name == "gemini" and has_gemini and name not in chain:
            chain.append(name)
        elif name == "openai" and has_openai and name not in chain:
            chain.append(name)
    return chain


def default_model(provider: str) -> str:
    if provider == "openrouter":
        return os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    if provider == "gemini":
        return os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
    return os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def active_provider_info() -> dict[str, str]:
    chain = provider_chain()
    if not chain:
        return {"provider": "none", "model": "not configured", "fallback": ""}
    fallback = ", ".join(chain[1:]) if len(chain) > 1 else ""
    p = chain[0]
    return {"provider": p, "model": default_model(p), "fallback": fallback}


def _openai_client_for(provider: str):
    from openai import OpenAI

    if provider == "openrouter":
        return OpenAI(
            api_key=os.environ["OPENROUTER_API_KEY"],
            base_url=os.environ.get("OPENROUTER_BASE_URL", OPENROUTER_BASE_URL),
            default_headers={
                "HTTP-Referer": os.environ.get("OPENROUTER_HTTP_REFERER", "http://localhost"),
                "X-Title": os.environ.get("OPENROUTER_APP_TITLE", "Google Photos Discovery Engine"),
            },
        )
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def _openai_compatible_chat(
    provider: str,
    *,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> tuple[str, str | None]:
    from openai import APIConnectionError, APIStatusError, AuthenticationError, RateLimitError

    client = _openai_client_for(provider)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
    except (AuthenticationError, RateLimitError, APIConnectionError) as exc:
        raise LLMProviderError(str(exc)) from exc
    except APIStatusError as exc:
        if exc.status_code in (401, 402, 403, 429, 500, 502, 503, 504):
            raise LLMProviderError(str(exc)) from exc
        raise

    choice = response.choices[0]
    content = choice.message.content or ""
    finish = getattr(choice, "finish_reason", None)
    return content, finish


def _messages_to_gemini(messages: list[dict[str, str]]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    system_chunks: list[str] = []
    contents: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role", "user")
        text = msg.get("content") or ""
        if role == "system":
            system_chunks.append(text)
        elif role == "assistant":
            contents.append({"role": "model", "parts": [{"text": text}]})
        else:
            contents.append({"role": "user", "parts": [{"text": text}]})
    system_instruction = None
    if system_chunks:
        system_instruction = {"parts": [{"text": "\n\n".join(system_chunks)}]}
    return system_instruction, contents


def _gemini_chat(
    *,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> tuple[str, str | None]:
    api_key = _gemini_key()
    if not api_key:
        raise LLMProviderError("GEMINI_API_KEY / GOOGLE_API_KEY not set")

    system_instruction, contents = _messages_to_gemini(messages)
    body: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }
    if system_instruction:
        body["systemInstruction"] = system_instruction

    url = f"{GEMINI_API_BASE}/models/{model}:generateContent"
    try:
        with httpx.Client(timeout=180.0) as client:
            resp = client.post(url, params={"key": api_key}, json=body)
    except httpx.RequestError as exc:
        raise LLMProviderError(str(exc)) from exc

    if resp.status_code in (401, 403, 429, 500, 502, 503, 504):
        raise LLMProviderError(f"Gemini HTTP {resp.status_code}: {resp.text[:400]}")
    if resp.status_code >= 400:
        resp.raise_for_status()

    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        block = (data.get("promptFeedback") or {}).get("blockReason")
        raise LLMProviderError(f"Gemini returned no candidates{f' ({block})' if block else ''}")

    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts)
    finish = candidates[0].get("finishReason")
    mapped_finish = "length" if finish == "MAX_TOKENS" else finish
    return text, mapped_finish


def chat_completion(
    provider: str,
    *,
    messages: list[dict[str, str]],
    max_tokens: int,
    model: str | None = None,
) -> tuple[str, str | None]:
    model = model or default_model(provider)
    if provider == "gemini":
        return _gemini_chat(model=model, messages=messages, max_tokens=max_tokens)
    if provider in ("openrouter", "openai"):
        return _openai_compatible_chat(
            provider, model=model, messages=messages, max_tokens=max_tokens
        )
    raise LLMProviderError(f"Unknown provider: {provider}")

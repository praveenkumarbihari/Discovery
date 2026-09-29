# Architecture decisions

## Gap audit (Part B — existing FastAPI build vs master prompt)

| Requirement | Current state | Gap | Effort | Priority |
|---|---|---|---|---|
| ≥3 sources, 2k raw, dedupe, PII, idempotent store | FastAPI live crawl only; no DuckDB; ~12 results/search | Large | L | P0 |
| 6-stage funnel + Pydantic extraction schema | 4-stage legacy JSON + old taxonomy | Large | L | P0 |
| LLM relevance → extraction with quote verify | Single-shot classify in `src/discovery_engine.py` | Large | L | P0 |
| Emergent taxonomy / clustering | None | Large | L | P1 |
| Opportunity scoring + weight sliders | None | Large | M | P1 |
| Insight cards (Stage 3 synthesis) | Partial `research_insights` | Medium | M | P1 |
| Streamlit multipage + Parquet demo | FastAPI search UI | Large | L | P1 |
| RAG Ask the corpus | None | Large | M | P2 |
| Validation gold set + kappa | None | Medium | M | P2 |
| HF Spaces deploy | Local only | Medium | S | P2 |

## Decisions

1. **Dual track:** Keep `src/web_app.py` (search-first demo) while building `engine/` CLI pipeline from the master prompt. Converge on DuckDB + Parquet as source of truth.
2. **LLM provider:** OpenRouter via OpenAI-compatible API first (existing `.env`); extend to Anthropic/Gemini in `engine/llm/client.py` when keys exist.
3. **Reddit:** PRAW if creds present later; Phase 2 uses public `.json` + delay (assignment-compliant fallback).
4. **Help Community / YouTube:** Best-effort collectors; pipeline must not fail if blocked (implemented as empty return + log).

# Methodology

## Purpose

Analyse **public** user feedback about **Google Photos vague-memory retrieval**: users remember partial cues but cannot reliably find photos.

## Data sources (target)

| Source | Status in repo |
|---|---|
| Google Play Store reviews | Implemented (`engine/collectors/play_store.py`) |
| Apple App Store reviews | Implemented (`engine/collectors/app_store.py`) |
| Reddit discussions | Implemented (`engine/collectors/reddit.py`); rate limits apply |
| Google Help Community | Best-effort stub (`help_community.py`) |
| YouTube comments | Requires `YOUTUBE_API_KEY` (stub) |
| CSV import | Manual fallback (`engine collect --csv`) |
| Stack Exchange / HN (legacy web UI) | `src/web_discovery/` for interactive search demo only |

## Processing (roadmap)

1. Clean: dedupe, PII scrub, length filter  
2. Keyword pre-filter (high recall)  
3. LLM Stage 1: relevance  
4. LLM Stage 2: structured extraction (6-stage funnel, cues, verified quotes)  
5. Taxonomy, clustering, segments, opportunity scoring  
6. LLM Stage 3: insight cards  

## Validation

- Target: 60-item stratified sample → human labels → accuracy + Cohen's kappa  
- Status: **Validation pending** (export via `engine validate` in Phase 6)

## Limitations

- Store reviews skew negative; Reddit skews power users; English-first filtering.  
- Automated Help/YouTube may be incomplete without API keys.  
- Live web demo (`src.web_app`) uses relevance heuristics, not full extraction pipeline.

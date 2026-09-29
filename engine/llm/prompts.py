PROMPT_VERSION = "1.0.0"

RELEVANCE_SYSTEM = """You classify public user feedback about Google Photos.
Retrieval = finding EXISTING photos with incomplete memory (not backup, storage, sharing, pricing, editing).
Return strict JSON matching the schema."""

EXTRACTION_SYSTEM = """You extract structured retrieval-failure data from Google Photos user feedback.
Funnel stages:
- express: user cannot turn memory into a query
- interpret: Photos misunderstands query / wrong or zero results / unsupported cue type
- recall_rank: right photo exists but buried or not ranked
- evaluate: results shown but user cannot pick the right one among near-duplicates
- refine: no good way to narrow after a miss; user scrolls manually
- other: not a retrieval problem

Only tag cues explicitly stated. evidence_quote MUST be a verbatim substring (<=40 words)."""

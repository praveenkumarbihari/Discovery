"""Pydantic v2 schemas for the vague-memory retrieval discovery pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .utils import utcnow

RawSource = Literal["play_store", "app_store", "reddit", "help_community", "youtube", "csv"]

FailureStage = Literal["express", "interpret", "recall_rank", "evaluate", "refine", "other"]

PhotoType = Literal[
    "person",
    "group_family",
    "pet",
    "place_travel",
    "event",
    "screenshot",
    "document_id",
    "receipt_bill",
    "medical",
    "object_product",
    "food",
    "video",
    "other",
]

CueRemembered = Literal[
    "person",
    "place",
    "event_occasion",
    "object",
    "text_in_image",
    "absolute_time",
    "relative_time",
    "season_weather",
    "emotion_mood",
    "source_app",
    "device",
    "color_visual",
    "activity",
    "other",
]

CueMissing = Literal["exact_date", "location", "album", "person_name", "keyword", "none_stated"]

FeatureMentioned = Literal[
    "search_bar",
    "ask_photos",
    "faces_people",
    "places_map",
    "things_categories",
    "ocr_text",
    "date_scrubber",
    "albums",
    "memories",
    "none",
]

Workaround = Literal[
    "manual_scroll",
    "date_scrubber",
    "whatsapp_or_other_app",
    "asked_someone",
    "other_gallery_app",
    "gave_up",
    "none_stated",
    "other",
]

Outcome = Literal["found", "not_found", "partially", "unknown"]

EmotionalStakes = Literal["low", "medium", "high"]

UserContext = Literal[
    "large_library",
    "long_time_user",
    "parent",
    "traveller",
    "professional_work",
    "elderly_or_helper",
    "student",
    "unknown",
]


class RawItem(BaseModel):
    id: str
    source: RawSource
    source_id: str
    url: str | None = None
    author_hash: str | None = None
    created_at: datetime | None = None
    rating: int | None = None
    title: str | None = None
    text: str
    parent_context: str | None = None
    country: str | None = None
    lang: str | None = None
    collected_at: datetime = Field(default_factory=utcnow)


class Relevance(BaseModel):
    id: str
    is_retrieval_related: bool
    is_vague_memory: bool
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(max_length=120)


class Extraction(BaseModel):
    id: str
    photo_type: PhotoType
    cues_remembered: list[CueRemembered]
    cue_evidence: dict[str, str] = Field(default_factory=dict)
    cues_missing: list[CueMissing]
    query_attempted: str | None = None
    failure_stage: FailureStage
    failure_stage_reason: str = Field(max_length=150)
    feature_mentioned: list[FeatureMentioned]
    workaround: list[Workaround]
    outcome: Outcome
    severity: int = Field(ge=1, le=5)
    emotional_stakes: EmotionalStakes
    user_context: list[UserContext]
    library_size_hint: str | None = None
    job_to_be_done: str
    evidence_quote: str = Field(max_length=280)
    quote_verified: bool = True


class InsightCard(BaseModel):
    title: str
    stage: str
    photo_types: list[str]
    evidence_stats: str
    root_cause_hypothesis: str
    representative_quotes: list[str]
    counter_evidence: str
    research_question: str

"""YouTube comments — requires YOUTUBE_API_KEY (Phase 6)."""

from __future__ import annotations

import os

from ..models import RawItem
from .base import Collector


class YouTubeCollector(Collector):
    name = "youtube"

    def collect(self) -> list[RawItem]:
        if not os.environ.get("YOUTUBE_API_KEY"):
            return []
        return []

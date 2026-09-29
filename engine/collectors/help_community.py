"""Google Help Community — best-effort; skipped if blocked."""

from __future__ import annotations

import httpx

from ..models import RawItem
from .base import Collector


class HelpCommunityCollector(Collector):
    name = "help_community"

    def collect(self) -> list[RawItem]:
        # Phase 2: placeholder; Google Help often blocks automated access.
        try:
            url = "https://support.google.com/photos/community"
            resp = httpx.get(url, timeout=15.0, headers={"User-Agent": "DiscoveryEngine/1.0"})
            if resp.status_code >= 400:
                return []
        except Exception:
            return []
        return []

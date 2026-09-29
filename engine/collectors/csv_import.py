from __future__ import annotations

import csv
from pathlib import Path

from ..models import RawItem
from ..utils import stable_id, utcnow
from .base import Collector


class CsvImportCollector(Collector):
    name = "csv"

    def __init__(self, path: Path):
        self.path = path

    def collect(self) -> list[RawItem]:
        items: list[RawItem] = []
        with self.path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for i, row in enumerate(reader):
                text = (row.get("text") or row.get("raw_text") or row.get("content") or "").strip()
                if not text:
                    continue
                source_id = row.get("source_id") or row.get("id") or str(i)
                items.append(
                    RawItem(
                        id=stable_id("csv", source_id),
                        source="csv",
                        source_id=source_id,
                        url=row.get("url"),
                        title=row.get("title"),
                        text=text,
                        collected_at=utcnow(),
                    )
                )
        return items

"""Read collected corpus from DuckDB for the web UI."""

from __future__ import annotations

from pathlib import Path

from engine.config_loader import load_config
from engine.db import DEFAULT_DB, connect, count_by_source, count_filtered, fetch_items, total_count

SOURCE_LABELS = {
    "play_store": "Google Play Store",
    "app_store": "Apple App Store",
    "reddit": "Reddit",
    "help_community": "Google Help Community",
    "youtube": "YouTube",
    "csv": "CSV import",
}


def db_path() -> Path:
    cfg = load_config()
    rel = cfg.get("paths", {}).get("duckdb", "data/engine.duckdb")
    root = Path(__file__).resolve().parent.parent
    return root / rel if not Path(rel).is_absolute() else Path(rel)


def corpus_available() -> bool:
    path = db_path()
    return path.is_file() and path.stat().st_size > 0


def get_stats() -> dict:
    if not corpus_available():
        return {"available": False, "total": 0, "by_source": [], "db_path": str(db_path())}
    con = connect(db_path())
    try:
        by_source = [
            {"source": src, "label": SOURCE_LABELS.get(src, src), "count": count}
            for src, count in count_by_source(con)
        ]
        return {
            "available": True,
            "total": total_count(con),
            "by_source": by_source,
            "db_path": str(db_path()),
        }
    finally:
        con.close()


def list_for_web(
    *,
    q: str | None = None,
    source: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    if not corpus_available():
        return {
            "available": False,
            "count": 0,
            "total": 0,
            "entries": [],
            "message": "No corpus yet. Run: py -3 -m engine collect --yes",
        }

    con = connect(db_path())
    try:
        total = count_filtered(con, q=q, source=source)
        rows = fetch_items(con, q=q, source=source, limit=limit, offset=offset)
    finally:
        con.close()

    entries = []
    for row in rows:
        src = row["source"]
        title = (row.get("title") or "").strip()
        body = (row["text"] or "").strip()
        raw_text = f"{title}\n\n{body}".strip() if title and title not in body else body
        entries.append(
            {
                "id": row["id"],
                "source": SOURCE_LABELS.get(src, src),
                "source_key": src,
                "raw_text": raw_text,
                "url": row.get("url"),
                "rating": row.get("rating"),
                "country": row.get("country"),
                "collected_at": row.get("collected_at"),
            }
        )

    return {
        "available": True,
        "count": len(entries),
        "total": total,
        "offset": offset,
        "limit": limit,
        "query": q or "",
        "source_filter": source,
        "entries": entries,
    }

"""DuckDB persistence for the discovery pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb

from .models import RawItem

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "engine.duckdb"


def connect(db_path: Path | str | None = None) -> duckdb.DuckDBPyConnection:
    path = Path(db_path or DEFAULT_DB)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    init_schema(con)
    return con


def init_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS raw_items (
            id VARCHAR PRIMARY KEY,
            source VARCHAR NOT NULL,
            source_id VARCHAR NOT NULL,
            url VARCHAR,
            author_hash VARCHAR,
            created_at TIMESTAMP,
            rating INTEGER,
            title VARCHAR,
            text VARCHAR NOT NULL,
            parent_context VARCHAR,
            country VARCHAR,
            lang VARCHAR,
            collected_at TIMESTAMP NOT NULL,
            payload JSON
        );
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS failures (
            id VARCHAR,
            stage VARCHAR,
            error VARCHAR,
            created_at TIMESTAMP DEFAULT current_timestamp
        );
        """
    )


def upsert_raw_items(con: duckdb.DuckDBPyConnection, items: list[RawItem]) -> int:
    if not items:
        return 0
    rows = [
        (
            i.id,
            i.source,
            i.source_id,
            i.url,
            i.author_hash,
            i.created_at,
            i.rating,
            i.title,
            i.text,
            i.parent_context,
            i.country,
            i.lang,
            i.collected_at,
            json.dumps(i.model_dump(mode="json")),
        )
        for i in items
    ]
    con.executemany(
        """
        INSERT OR REPLACE INTO raw_items
        (id, source, source_id, url, author_hash, created_at, rating, title, text,
         parent_context, country, lang, collected_at, payload)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return len(rows)


def count_by_source(con: duckdb.DuckDBPyConnection) -> list[tuple[str, int]]:
    return con.execute(
        "SELECT source, COUNT(*) FROM raw_items GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall()


def total_count(con: duckdb.DuckDBPyConnection) -> int:
    row = con.execute("SELECT COUNT(*) FROM raw_items").fetchone()
    return int(row[0]) if row else 0


def fetch_items(
    con: duckdb.DuckDBPyConnection,
    *,
    q: str | None = None,
    source: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    clauses = ["1=1"]
    params: list[Any] = []
    if source:
        clauses.append("source = ?")
        params.append(source)
    if q and q.strip():
        clauses.append("text ILIKE ?")
        params.append(f"%{q.strip()}%")

    where = " AND ".join(clauses)
    params.extend([limit, offset])
    rows = con.execute(
        f"""
        SELECT id, source, source_id, url, title, text, rating, country, collected_at
        FROM raw_items
        WHERE {where}
        ORDER BY collected_at DESC
        LIMIT ? OFFSET ?
        """,
        params,
    ).fetchall()

    return [
        {
            "id": r[0],
            "source": r[1],
            "source_id": r[2],
            "url": r[3],
            "title": r[4],
            "text": r[5],
            "rating": r[6],
            "country": r[7],
            "collected_at": r[8].isoformat() if r[8] else None,
        }
        for r in rows
    ]


def count_filtered(
    con: duckdb.DuckDBPyConnection,
    *,
    q: str | None = None,
    source: str | None = None,
) -> int:
    clauses = ["1=1"]
    params: list[Any] = []
    if source:
        clauses.append("source = ?")
        params.append(source)
    if q and q.strip():
        clauses.append("text ILIKE ?")
        params.append(f"%{q.strip()}%")
    where = " AND ".join(clauses)
    row = con.execute(f"SELECT COUNT(*) FROM raw_items WHERE {where}", params).fetchone()
    return int(row[0]) if row else 0

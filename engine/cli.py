"""Typer CLI: collect | filter | extract | enrich | cluster | score | export | validate | all"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .collectors.app_store import AppStoreCollector
from .collectors.csv_import import CsvImportCollector
from .collectors.help_community import HelpCommunityCollector
from .collectors.play_store import PlayStoreCollector
from .collectors.reddit import RedditCollector
from .collectors.youtube import YouTubeCollector
from .config_loader import load_config
from .db import connect, count_by_source, upsert_raw_items
from .llm.client import chat_json
from .llm.prompts import PROMPT_VERSION, RELEVANCE_SYSTEM
from .pipeline.clean import dedupe_items, length_filter
from .pipeline.keyword_filter import filter_by_keywords

app = typer.Typer(add_completion=False, help="Google Photos vague-memory discovery engine")
console = Console()


def _load_dotenv() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        import os

        if k.strip() and k.strip() not in os.environ:
            os.environ[k.strip()] = v.strip().strip('"').strip("'")


@app.command("collect")
def collect(
    csv_path: Path | None = typer.Option(None, "--csv", help="Import manual CSV"),
    yes: bool = typer.Option(True, "--yes/--no", help="Skip confirmation"),
    keyword_only: bool = typer.Option(
        False,
        "--keyword-only",
        help="Store only keyword-matching rows (default: store all deduped items)",
    ),
    min_words: int | None = typer.Option(
        None,
        "--min-words",
        help="Minimum words per item (overrides config collection.min_words)",
    ),
    skip_reddit: bool = typer.Option(
        False,
        "--skip-reddit",
        help="Skip Reddit (faster collect; Play + App Store only)",
    ),
    reddit_only: bool = typer.Option(
        False,
        "--reddit-only",
        help="Collect Reddit only (append to DuckDB)",
    ),
):
    """Collect raw items from configured public sources into DuckDB."""
    _load_dotenv()
    cfg = load_config()
    c = cfg["collection"]
    all_items = []
    reddit_cfg = c.get("reddit") or {}
    play_cfg = c.get("play_store") or {}

    collectors = [
        PlayStoreCollector(
            play_cfg["app_id"],
            play_cfg["countries"],
            play_cfg.get("per_sort_limit", 500),
            sorts=play_cfg.get("sorts"),
        ),
        AppStoreCollector(
            c["app_store"]["app_id"],
            c["app_store"]["countries"],
            c["app_store"]["max_pages"],
        ),
        RedditCollector(
            reddit_cfg["subreddits"],
            reddit_cfg["search_queries"],
            reddit_cfg.get("request_delay_seconds", 2.0),
            limit_per_query=reddit_cfg.get("limit_per_query", 100),
            pages_per_query=reddit_cfg.get("pages_per_query", 3),
        ),
        HelpCommunityCollector(),
        YouTubeCollector(),
    ]
    if reddit_only:
        collectors = [c for c in collectors if c.name == "reddit"]
    elif skip_reddit:
        collectors = [c for c in collectors if c.name != "reddit"]
    if csv_path:
        collectors.append(CsvImportCollector(csv_path))

    for col in collectors:
        try:
            batch = col.collect()
            console.print(f"[green]{col.name}[/green]: {len(batch)} items")
            all_items.extend(batch)
        except Exception as exc:
            console.print(f"[yellow]{col.name} failed[/yellow]: {exc}")

    all_items = dedupe_items(all_items)
    terms = cfg["collection"]["keyword_filter"]["terms"]
    word_min = min_words if min_words is not None else int(c.get("min_words", 15))
    all_items = length_filter(all_items, min_words=word_min, strong_keywords=terms)
    filtered, pass_rate = filter_by_keywords(all_items, terms)
    console.print(f"Keyword filter pass rate: {pass_rate:.1%} ({len(filtered)}/{len(all_items) or 1})")

    store_mode = "keyword_filtered" if keyword_only else c.get("store_mode", "all")
    to_store = filtered if store_mode == "keyword_filtered" else all_items
    console.print(
        f"Storing [bold]{len(to_store)}[/bold] rows "
        f"({'keyword matches only' if store_mode == 'keyword_filtered' else 'all deduped items'})"
    )

    con = connect(cfg["paths"]["duckdb"])
    upsert_raw_items(con, to_store)
    table = Table(title="Raw items in DuckDB")
    table.add_column("source")
    table.add_column("count")
    for source, count in count_by_source(con):
        table.add_row(source, str(count))
    console.print(table)


@app.command("filter")
def filter_cmd():
    """Run keyword / clean filters on stored raw items (Phase 2 stub)."""
    console.print("Use `collect` — filtering is applied during collection in Phase 2.")


@app.command("llm-test")
def llm_test():
    """One cheap-model JSON call to verify LLM configuration."""
    _load_dotenv()
    cfg = load_config()
    model = cfg["llm"]["cheap_model"]
    payload, meta = chat_json(
        model=model,
        system=RELEVANCE_SYSTEM,
        user='Classify: {"id":"demo","text":"I cannot find an old screenshot in Google Photos search."}',
        prompt_version=PROMPT_VERSION,
    )
    console.print(json.dumps({"response": payload, "meta": meta}, indent=2))


@app.command("extract")
def extract():
    typer.echo("Phase 3: relevance + extraction pipeline (not implemented yet).")


@app.command("all")
def run_all():
    typer.echo("Phase 10: end-to-end pipeline (collect only available in Phase 2).")
    collect(csv_path=None, yes=True)


if __name__ == "__main__":
    app()

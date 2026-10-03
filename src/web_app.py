"""Browser UI for Google Photos Discovery Engine."""

from __future__ import annotations

import os
import time
import webbrowser

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .discovery_engine import ROOT, _default_model, analyze_posts, load_dotenv, load_json
from .llm_providers import active_provider_info
from .feedback_input import AnalyzeBody, SOURCE_PRESETS, entries_to_posts, posts_to_entries
from .server_util import ensure_port_available
from .research_questions import load_catalog, suggested_searches
from .web_discovery.discover import (
    DEFAULT_QUERY,
    DiscoverRequest,
    discover_feedback,
    load_cached_discovery,
)

API_VERSION = "2.1.0"
STATIC_DIR = ROOT / "static"
load_dotenv()

# When behind nginx at e.g. /projects/discovery/, set DISCOVERY_BASE_PATH=/projects/discovery/
_DISCOVERY_BASE_PATH = os.environ.get("DISCOVERY_BASE_PATH", "").strip()
if _DISCOVERY_BASE_PATH and not _DISCOVERY_BASE_PATH.endswith("/"):
    _DISCOVERY_BASE_PATH = f"{_DISCOVERY_BASE_PATH}/"

app = FastAPI(title="Google Photos Discovery Engine", version=API_VERSION)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    print(
        f"[api] {response.status_code} {request.method} {request.url.path} "
        f"({elapsed_ms:.0f}ms)",
        flush=True,
    )
    return response


@app.get("/")
def index():
    headers = {"Cache-Control": "no-cache, must-revalidate"}
    if not _DISCOVERY_BASE_PATH:
        return FileResponse(STATIC_DIR / "index.html", headers=headers)
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    inject = f'    <base href="{_DISCOVERY_BASE_PATH}" />\n'
    html = html.replace("<head>", f"<head>\n{inject}", 1)
    return HTMLResponse(html, headers=headers)


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "version": API_VERSION,
        "endpoints": {
            "discover": True,
            "analyze": True,
            "meta": True,
        },
    }


@app.get("/api/meta")
def meta():
    llm = active_provider_info()
    return {
        "version": API_VERSION,
        "model": _default_model(),
        "provider": llm["provider"],
        "llm_fallback": llm.get("fallback") or None,
        "source_presets": list(SOURCE_PRESETS),
        "max_entries": 50,
        "max_discover_results": 50,
        "storage_mode": "live_web_only",
        "default_discover_query": DEFAULT_QUERY,
        "discover_sources": [
            {"id": "stackexchange", "label": "Stack Exchange Q&A"},
            {"id": "hackernews", "label": "Hacker News"},
            {"id": "playstore", "label": "Google Play reviews"},
            {"id": "reddit", "label": "Reddit (archive API)"},
        ],
    }


@app.get("/api/research-questions")
def research_questions():
    catalog = load_catalog()
    return {
        "catalog": catalog,
        "suggested_searches": suggested_searches(),
    }


@app.get("/api/sample")
@app.get("/api/sample-input")
def sample():
    posts = load_json(ROOT / "data" / "sample_input.json")
    return {"entries": posts_to_entries(posts)}


@app.get("/api/discover/last")
def discover_last():
    cached = load_cached_discovery()
    if cached is None:
        return JSONResponse({"entries": [], "count": 0, "cached": False})
    cached = dict(cached)
    cached["cached"] = True
    return cached


@app.post("/api/discover")
def discover(body: DiscoverRequest):
    print(
        f"[discover] query={body.query!r} limit={body.limit} sources={body.sources}",
        flush=True,
    )
    try:
        result = discover_feedback(body)
        print(f"[discover] found {result.get('count', 0)} posts", flush=True)
        return result
    except Exception as exc:
        print(f"[discover] error: {exc}", flush=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/analyze")
def analyze(body: AnalyzeBody):
    print(f"[analyze] entries={len(body.entries)} dry_run={body.dry_run}", flush=True)
    try:
        posts = entries_to_posts(body.entries)
        result = analyze_posts(posts, dry_run=body.dry_run)
        print(f"[analyze] ok total_analyzed={result.get('total_analyzed')}", flush=True)
        return result
    except Exception as exc:
        print(f"[analyze] error: {exc}", flush=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def main() -> None:
    load_dotenv()
    host = "127.0.0.1"
    port = 8765
    ensure_port_available(host, port, auto_free=True)
    url = f"http://{host}:{port}/"
    print(f"Discovery Engine UI v{API_VERSION}: {url}", flush=True)
    print(
        "API: POST /api/discover, POST /api/analyze, GET /api/health (live web scrape, no DuckDB)",
        flush=True,
    )
    print("Press Ctrl+C to stop.", flush=True)
    webbrowser.open(url)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

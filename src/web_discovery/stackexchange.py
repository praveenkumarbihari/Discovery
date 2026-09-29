from __future__ import annotations

import httpx

from .relevance import is_relevant, normalize_text

STACK_SITES = ("android", "superuser", "webapps", "askdifferent")
API = "https://api.stackexchange.com/2.3/search/advanced"


def fetch_stackexchange_posts(query: str, *, limit: int = 10) -> list[dict]:
    headers = {"User-Agent": "DiscoveryEngine/1.0 (research)"}
    search_q = f'"google photos" {query} search find filter'.strip()
    per_site = max(3, limit)
    results: list[dict] = []
    seen: set[int] = set()

    with httpx.Client(headers=headers, timeout=30.0) as client:
        for site in STACK_SITES:
            response = client.get(
                API,
                params={
                    "order": "desc",
                    "sort": "relevance",
                    "q": search_q,
                    "site": site,
                    "pagesize": min(per_site, 15),
                    "filter": "withbody",
                },
            )
            response.raise_for_status()
            items = response.json().get("items") or []

            for item in items:
                question_id = int(item.get("question_id") or 0)
                if not question_id or question_id in seen:
                    continue
                seen.add(question_id)

                title = normalize_text(item.get("title") or "")
                body = normalize_text(item.get("body") or "")
                text = f"{title}\n\n{body}".strip() if body else title
                if not is_relevant(text, query):
                    continue

                link = item.get("link") or f"https://{site}.stackexchange.com/questions/{question_id}"
                results.append(
                    {
                        "id": f"stackexchange_{site}_{question_id}",
                        "source": f"Stack Exchange ({site})",
                        "raw_text": text[:8000],
                        "url": link,
                        "discovered_from": "stackexchange",
                    }
                )
                if len(results) >= limit:
                    return results

    return results

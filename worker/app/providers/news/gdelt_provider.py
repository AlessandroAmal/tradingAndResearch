"""GDELT 2.0 Doc API news provider (free, no API key).

Queries the GDELT article search endpoint for recent articles matching the
configured keywords. GDELT is rate-limited and occasionally returns
non-JSON on overload, so we handle errors defensively.

NOTE (CLAUDE.md): verify GDELT's current endpoint/limits before relying on
it in production — terms change. Docs: https://api.gdeltproject.org/api/v2/doc/doc
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from ...logging_setup import get_logger
from .base import NewsItem, NewsProvider

log = get_logger("provider.news.gdelt")

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


class GDELTNewsProvider(NewsProvider):
    name = "gdelt"

    def __init__(self, timespan: str = "1d", max_records: int = 60, timeout: float = 25.0):
        self._timespan = timespan
        self._max_records = max_records
        self._timeout = timeout

    def fetch(self, keywords: list[str]) -> list[NewsItem]:
        if not keywords:
            return []
        # OR-join keywords; quote multi-word phrases.
        terms = [f'"{k}"' if " " in k else k for k in keywords]
        query = "(" + " OR ".join(terms) + ") sourcelang:english"
        params = {
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "timespan": self._timespan,
            "maxrecords": str(self._max_records),
            "sort": "DateDesc",
        }
        try:
            resp = httpx.get(GDELT_URL, params=params, timeout=self._timeout)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"GDELT request failed: {exc}") from exc

        try:
            data = resp.json()
        except ValueError as exc:  # GDELT returns plain text on overload
            raise RuntimeError(f"GDELT returned non-JSON (rate limited?): {exc}") from exc

        articles = data.get("articles", []) if isinstance(data, dict) else []
        items: list[NewsItem] = []
        for a in articles:
            url = a.get("url")
            title = a.get("title")
            if not url or not title:
                continue
            items.append(
                NewsItem(
                    title=title.strip(),
                    url=url,
                    source=a.get("domain") or "gdelt",
                    published_at=_parse_seendate(a.get("seendate")),
                    summary=None,
                )
            )
        log.info("GDELT returned %d articles", len(items))
        return items


def _parse_seendate(raw: object) -> datetime | None:
    # GDELT seendate format: 20260620T130000Z
    if not isinstance(raw, str):
        return None
    try:
        return datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None

"""Fresh per-stock news ("Cosa muove il titolo") via Google News RSS.

For a single stock we query by COMPANY NAME + TICKER (e.g. "Tesla" OR TSLA) so we
catch what actually moves it — regulatory probes (NHTSA), deliveries, product —
which generic universe tagging can miss. Free, no key; defensive (errors -> []).

The fetch is isolated in `_parse_feed`/feedparser so tests mock it (no network).
Read-only context, never a signal.
"""
from __future__ import annotations

from datetime import datetime, timezone
from time import struct_time
from urllib.parse import quote_plus

import feedparser

from ..logging_setup import get_logger

log = get_logger("decision.stock_news")
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


def recent_news(name: str, ticker: str, *, days: int = 7, limit: int = 5) -> list[dict]:
    """Recent headlines for a stock by name + ticker, newest first. [] on failure."""
    terms = []
    if name:
        terms.append(f'"{name}"')
    if ticker:
        terms.append(ticker)
    if not terms:
        return []
    query = f"({' OR '.join(terms)}) when:{days}d"
    url = f"{GOOGLE_NEWS_RSS}?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    try:
        entries = _parse_feed(url)
    except Exception as exc:  # noqa: BLE001
        log.warning("stock news %s failed: %s", ticker, exc)
        return []
    out: list[dict] = []
    for e in entries[:limit]:
        title = (e.get("title") or "").strip()
        link = e.get("link")
        if not title or not link:
            continue
        out.append({
            "title": title, "url": link,
            "source": _source(e),
            "published_at": _ts(e.get("published_parsed")),
        })
    return out


def _parse_feed(url: str) -> list:
    parsed = feedparser.parse(url)
    return list(getattr(parsed, "entries", []) or [])


def _source(entry) -> str:
    src = entry.get("source")
    if isinstance(src, dict) and src.get("title"):
        return src["title"]
    return "Google News"


def _ts(t: struct_time | None) -> str | None:
    if not t:
        return None
    try:
        return datetime(*t[:6], tzinfo=timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None

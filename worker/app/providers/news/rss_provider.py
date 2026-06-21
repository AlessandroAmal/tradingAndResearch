"""RSS news provider (configurable feed list).

Reads the feeds defined in config (`news.rss.feeds`). One feed failing
does not abort the others — failures are logged and skipped so the
dashboard degrades gracefully if a source is down.
"""
from __future__ import annotations

from datetime import datetime, timezone
from time import struct_time

import feedparser

from ...logging_setup import get_logger
from .base import NewsItem, NewsProvider

log = get_logger("provider.news.rss")


class RSSNewsProvider(NewsProvider):
    name = "rss"

    def __init__(self, feeds: list[dict[str, str]]):
        # feeds: [{"name": ..., "url": ...}, ...]
        self._feeds = feeds or []

    def fetch(self, keywords: list[str]) -> list[NewsItem]:
        items: list[NewsItem] = []
        kw_lower = [k.lower() for k in keywords]
        for feed in self._feeds:
            url = feed.get("url")
            name = feed.get("name") or url or "rss"
            if not url:
                continue
            try:
                parsed = feedparser.parse(url)
            except Exception as exc:  # noqa: BLE001 — isolate per-feed failures
                log.error("RSS feed failed (%s): %s", name, exc)
                continue
            if getattr(parsed, "bozo", False) and not parsed.entries:
                log.warning("RSS feed unreadable or empty: %s", name)
                continue

            for entry in parsed.entries:
                title = (entry.get("title") or "").strip()
                link = entry.get("link")
                if not title or not link:
                    continue
                # Keyword filter: keep items mentioning a tracked keyword
                # (RSS feeds are broad; this trims noise before AI tagging).
                if kw_lower and not _matches(title, entry.get("summary", ""), kw_lower):
                    continue
                items.append(
                    NewsItem(
                        title=title,
                        url=link,
                        source=name,
                        published_at=_parse_struct(entry.get("published_parsed")),
                        summary=(entry.get("summary") or None),
                    )
                )
        log.info("RSS returned %d items from %d feeds", len(items), len(self._feeds))
        return items


def _matches(title: str, summary: str, kw_lower: list[str]) -> bool:
    hay = f"{title} {summary}".lower()
    return any(k in hay for k in kw_lower)


def _parse_struct(t: struct_time | None) -> datetime | None:
    if not t:
        return None
    try:
        return datetime(*t[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None

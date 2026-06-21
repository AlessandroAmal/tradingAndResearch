"""News-backed FigureSource: per-figure Google News RSS search + optional
official press feed.

This reuses the M3 news mechanics (Google News RSS, feedparser) rather than
adding new paid feeds. For each figure we run one bounded RSS search built
from its keywords, and — when configured — also read its official press RSS
(e.g. the Fed press feed for Powell). Free, no API key.

NOTE (CLAUDE.md): verify Google News RSS availability/terms before relying
on it in production — it is unofficial and can change.
"""
from __future__ import annotations

from datetime import datetime, timezone
from time import struct_time
from urllib.parse import quote_plus

import feedparser

from ...logging_setup import get_logger
from .base import FigureStatement, FigureSource

log = get_logger("provider.figures.news")

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


class NewsFigureSource(FigureSource):
    name = "news"

    def __init__(self, timespan_days: int = 2, max_per_feed: int = 20):
        self._timespan_days = timespan_days
        self._max_per_feed = max_per_feed

    def fetch(self, figure: dict) -> list[FigureStatement]:
        name = figure.get("name")
        if not name:
            return []
        role = figure.get("role")
        keywords = figure.get("keywords") or [name]

        items: list[FigureStatement] = []
        items.extend(self._fetch_google_news(name, role, keywords))

        press = figure.get("press_rss")
        if press:
            items.extend(self._fetch_press(name, role, press))

        log.info("Figure '%s': %d raw statements", name, len(items))
        return items

    # --- Google News RSS search --------------------------------------
    def _fetch_google_news(self, name, role, keywords) -> list[FigureStatement]:
        terms = [f'"{k}"' if " " in k else k for k in keywords]
        query = f"({' OR '.join(terms)}) when:{self._timespan_days}d"
        url = (
            f"{GOOGLE_NEWS_RSS}?q={quote_plus(query)}"
            "&hl=en-US&gl=US&ceid=US:en"
        )
        parsed = _safe_parse(url, label=f"google-news({name})")
        out: list[FigureStatement] = []
        for entry in parsed[: self._max_per_feed]:
            title = (entry.get("title") or "").strip()
            link = entry.get("link")
            if not title or not link:
                continue
            out.append(
                FigureStatement(
                    figure=name,
                    text=title,
                    source=_entry_source(entry, "Google News"),
                    url=link,
                    stated_at=_parse_struct(entry.get("published_parsed")),
                    role=role,
                )
            )
        return out

    # --- official press feed -----------------------------------------
    def _fetch_press(self, name, role, press_url) -> list[FigureStatement]:
        parsed = _safe_parse(press_url, label=f"press({name})")
        out: list[FigureStatement] = []
        for entry in parsed[: self._max_per_feed]:
            title = (entry.get("title") or "").strip()
            link = entry.get("link")
            if not title or not link:
                continue
            out.append(
                FigureStatement(
                    figure=name,
                    text=title,
                    source="official press",
                    url=link,
                    stated_at=_parse_struct(entry.get("published_parsed")),
                    role=role,
                )
            )
        return out


def _safe_parse(url: str, label: str) -> list:
    try:
        parsed = feedparser.parse(url)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"{label} feed failed: {exc}") from exc
    if getattr(parsed, "bozo", False) and not parsed.entries:
        raise RuntimeError(f"{label} feed unreadable")
    return parsed.entries


def _entry_source(entry, default: str) -> str:
    src = entry.get("source")
    if isinstance(src, dict) and src.get("title"):
        return src["title"]
    return default


def _parse_struct(t: struct_time | None) -> datetime | None:
    if not t:
        return None
    try:
        return datetime(*t[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None

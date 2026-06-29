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

# Default statement cues: bias the query toward things the figure SAID, not news
# about their institution. Configurable via news.figures_filter.statement_cues.
DEFAULT_CUES = [
    "said", "says", "statement", "remarks", "speech", "testimony",
    "comments", "warns", "signals", "tells", "told", "reiterates",
]
# Default non-statement markers to drop (obituaries etc.). Configurable.
DEFAULT_DROP = [
    "obituary", "dies", "died", "death", "funeral", "necrolog",
    "passes away", "passed away",
]


class NewsFigureSource(FigureSource):
    name = "news"

    def __init__(self, timespan_days: int = 2, max_per_feed: int = 20,
                 filter_cfg: dict | None = None):
        self._timespan_days = timespan_days
        self._max_per_feed = max_per_feed
        fc = dict(filter_cfg or {})
        self._require_name = bool(fc.get("require_name_in_title", True))
        self._cues = [c.lower() for c in fc.get("statement_cues", DEFAULT_CUES)]
        self._drop = [d.lower() for d in fc.get("drop_terms", DEFAULT_DROP)]
        # Context terms let a SURNAME-only match through only when the title also
        # names the figure's domain (e.g. "Powell" + "Fed") — kills homonyms
        # (Lucy/Daryl Powell rugby/UK-politics). Per-figure overrides this default.
        self._context_default = [c.lower() for c in fc.get("context_terms", [])]

    def fetch(self, figure: dict) -> list[FigureStatement]:
        name = figure.get("name")
        if not name:
            return []
        role = figure.get("role")
        keywords = figure.get("keywords") or [name]
        match_terms = _match_terms(figure)
        context_terms = [c.lower() for c in (figure.get("context_terms") or self._context_default)]

        items: list[FigureStatement] = []
        items.extend(self._fetch_google_news(name, role, match_terms, context_terms))

        press = figure.get("press_rss")
        if press:
            items.extend(self._fetch_press(name, role, press))

        log.info("Figure '%s': %d statements after filtering", name, len(items))
        return items

    # --- Google News RSS search --------------------------------------
    def _fetch_google_news(self, name, role, match_terms, context_terms) -> list[FigureStatement]:
        # Query: require a name/match term AND (when configured) a statement cue,
        # so we surface things the figure SAID, not generic institution news.
        names = " OR ".join(f'"{t}"' if " " in t else t for t in match_terms)
        cues = f" ({' OR '.join(self._cues)})" if self._cues else ""
        query = f"({names}){cues} when:{self._timespan_days}d"
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
            if not self._keep(title, match_terms, context_terms):
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

    def _keep(self, title: str, match_terms: list[str], context_terms: list[str]) -> bool:
        low = title.lower()
        if any(bad in low for bad in self._drop):
            return False        # drop obvious non-statements (obituaries etc.)
        if not self._require_name:
            return True
        full = [t.lower() for t in match_terms if " " in t]      # e.g. "jerome powell"
        short = [t.lower() for t in match_terms if " " not in t]  # e.g. "powell"
        if any(t in low for t in full):
            return True         # full distinctive name -> strong match
        # A surname/single-word match needs domain CONTEXT (kills homonyms:
        # Lucy/Daryl Powell, St Helens rugby, etc.). No context configured for a
        # single-word figure (e.g. an institution) -> accept the bare match.
        if any(t in low for t in short):
            return (not context_terms) or any(c in low for c in context_terms)
        return False

    # --- official press feed -----------------------------------------
    def _fetch_press(self, name, role, press_url) -> list[FigureStatement]:
        parsed = _safe_parse(press_url, label=f"press({name})")
        out: list[FigureStatement] = []
        for entry in parsed[: self._max_per_feed]:
            title = (entry.get("title") or "").strip()
            link = entry.get("link")
            if not title or not link:
                continue
            # Official press is curated, but still drop obvious non-statements.
            if any(bad in title.lower() for bad in self._drop):
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


def _match_terms(figure: dict) -> list[str]:
    """Terms that must appear in a title for it to count as this figure's
    statement. Config `match_terms` wins; otherwise derive from the name
    (full name + surname) so 'Powell signals…' matches but 'NY Fed …' doesn't."""
    explicit = figure.get("match_terms")
    if explicit:
        return [str(t) for t in explicit]
    name = figure.get("name") or ""
    terms = [name]
    tokens = name.split()
    if len(tokens) > 1:
        terms.append(tokens[-1])   # surname (e.g. "Powell")
    return [t for t in terms if t]


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

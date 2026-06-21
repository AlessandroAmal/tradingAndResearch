"""NewsProvider interface.

Every news source sits behind this interface so providers (GDELT, RSS,
optional NewsAPI) can be swapped or combined without touching ingestion
(CLAUDE.md §4). Providers return raw, UNtagged items — the AI tagging
layer fills in themes/instruments later.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    source: str
    published_at: datetime | None  # tz-aware UTC when known
    summary: str | None = None     # provider-supplied snippet (if any)


@runtime_checkable
class NewsProvider(Protocol):
    name: str

    def fetch(self, keywords: list[str]) -> list[NewsItem]:
        """Return recent news items relevant to `keywords`.

        Must raise on hard failure so the ingestion job can log it and
        the dashboard degrades gracefully; transient emptiness is fine.
        """
        ...

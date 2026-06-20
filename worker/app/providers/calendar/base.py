"""CalendarProvider interface.

Economic/event calendar sources sit behind this interface so a provider
(FMP today) can be swapped or replaced by a manual seed (CLAUDE.md §4).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class CalendarEvent:
    title: str
    event_time: datetime          # tz-aware, UTC
    category: str | None = None    # economic|earnings|dividend|macro
    country: str | None = None
    importance: str | None = None  # low|medium|high
    actual: str | None = None
    forecast: str | None = None
    previous: str | None = None
    symbols: list[str] = field(default_factory=list)
    source: str = ""


@runtime_checkable
class CalendarProvider(Protocol):
    name: str

    def fetch_events(self, from_date: str, to_date: str) -> list[CalendarEvent]:
        """Return calendar events in [from_date, to_date] (YYYY-MM-DD).

        Must raise on hard failure so the ingestion job can log it and
        the dashboard can degrade gracefully.
        """
        ...

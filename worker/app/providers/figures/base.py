"""FigureSource interface (M4 key-figures tracker).

Every source of figure statements/mentions sits behind this interface so
implementations (per-figure news search, official press feeds, future
X/IR feeds) can be swapped without touching ingestion (CLAUDE.md §4).

Sources return raw, UNmapped statements; the AI impact-mapping layer fills
affected_instruments / why_it_matters later.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class FigureStatement:
    figure: str                     # canonical figure name (from config)
    text: str                       # statement / headline text
    source: str                     # source name (feed/domain)
    url: str | None                 # link, if any
    stated_at: datetime | None      # tz-aware UTC when known
    role: str | None = None         # figure's role (from config)


@runtime_checkable
class FigureSource(Protocol):
    name: str

    def fetch(self, figure: dict[str, Any]) -> list[FigureStatement]:
        """Return recent statements/mentions for one configured figure.

        `figure` is a config dict: {name, role, keywords[], press_rss?}.
        Must raise on hard failure so the ingestion job can isolate and
        log it per-figure; transient emptiness is fine.
        """
        ...

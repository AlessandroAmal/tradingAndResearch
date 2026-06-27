"""PositioningProvider interface (COT / futures positioning).

A new free data source (CFTC) behind an interface so it can be swapped without
touching the decision board (CLAUDE.md §4). Returns weekly net positioning for a
trader category; the board turns it into a percentile + a contrarian state.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class CotReport:
    report_date: date
    long: float | None
    short: float | None
    net: float | None        # long - short (the category's net position)
    open_interest: float | None
    source: str


@runtime_checkable
class PositioningProvider(Protocol):
    name: str

    def fetch_history(self, market_query: str, *, lookback_weeks: int) -> list[CotReport]:
        """Weekly COT reports for a market (e.g. 'EURO FX'), oldest→newest.

        Must raise on hard failure so the caller can log it and degrade (the
        board simply omits the positioning block when unavailable).
        """
        ...

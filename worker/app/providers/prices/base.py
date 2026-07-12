"""PriceProvider interface.

Every price source sits behind this interface so providers can be
swapped without touching ingestion/storage (CLAUDE.md §4).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class PriceBar:
    symbol: str
    ts: datetime          # bar timestamp (tz-aware, UTC)
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None
    source: str


@runtime_checkable
class PriceProvider(Protocol):
    name: str

    def fetch_history(self, symbol: str, days: int) -> list[PriceBar]:
        """Return up to `days` of daily OHLCV bars for `symbol`.

        Implementations must raise on hard failure so the ingestion job
        can log it clearly; they should not silently return partial data
        without signalling.
        """
        ...

    def latest_price(self, symbol: str) -> float | None:
        """Latest available price (near-live), or None on failure.

        Used by the event experiment to stamp intraday entry/exit prices. Free
        sources are delayed and thin near data releases — the caller labels this
        (t+5min prices are optimistic if spread/slippage isn't modelled).
        """
        ...

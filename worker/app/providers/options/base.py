"""OptionsProvider interface (M5).

Options sources sit behind this interface so yfinance (free, today) can be
swapped for Polygon/Tradier later without touching the quant/ingestion
(CLAUDE.md §4). Providers return RAW quotes only (strike, bid/ask, last,
volume, OI) — IV and Greeks are RECALCULATED in `app.options`, since Yahoo's
impliedVolatility is unreliable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class OptionQuote:
    option_type: str          # 'call' | 'put'
    strike: float
    bid: float | None
    ask: float | None
    last: float | None
    volume: float | None
    open_interest: float | None


@runtime_checkable
class OptionsProvider(Protocol):
    name: str

    def get_spot(self, underlying: str) -> float | None:
        """Latest spot for the underlying (needed for IV/Greeks)."""
        ...

    def list_expiries(self, underlying: str) -> list[str]:
        """Expiry dates 'YYYY-MM-DD'. Empty when the underlying has no options
        (e.g. FX/crypto/index on yfinance) — caller degrades gracefully."""
        ...

    def fetch_chain(self, underlying: str, expiry: str) -> list[OptionQuote]:
        """Calls + puts for one expiry. Raise on hard failure so the job can
        log it and continue with other underlyings."""
        ...

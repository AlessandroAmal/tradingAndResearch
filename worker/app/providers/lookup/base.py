"""Symbol-lookup provider interface — resolve an ISIN (or free-text) to ticker(s).

ISIN→ticker resolution on free sources is UNRELIABLE and can be ambiguous, so a
provider returns a list of candidates with whatever metadata it found; the caller
(and ultimately the user) decides. Nothing here ever guesses silently.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class LookupResult:
    symbol: str
    name: str | None = None
    currency: str | None = None
    exchange: str | None = None
    quote_type: str | None = None      # EQUITY | ETF | CURRENCY | …
    isin: str | None = None            # echoed back when the query was an ISIN
    source: str = "unknown"


@runtime_checkable
class SymbolLookupProvider(Protocol):
    name: str

    def resolve(self, query: str) -> list[LookupResult]:
        """Return candidate matches for an ISIN or free-text query (may be empty)."""
        ...

    def currency_for(self, symbol: str) -> str | None:
        """Best-effort native quote currency for a ticker, or None."""
        ...

    def describe(self, symbol: str) -> LookupResult | None:
        """Best-effort name + currency + exchange for a known ticker (the reliable
        path when ISIN search is blocked: the user gives the ticker, we confirm)."""
        ...

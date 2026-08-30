"""Symbol-lookup providers (ISIN/text → ticker). Behind an interface so the
source can be swapped without touching the portfolio module (CLAUDE.md rule 4)."""
from __future__ import annotations

from .base import LookupResult, SymbolLookupProvider
from .yahoo_provider import YahooLookupProvider

__all__ = ["LookupResult", "SymbolLookupProvider", "YahooLookupProvider", "build_lookup_provider"]


def build_lookup_provider(name: str) -> SymbolLookupProvider:
    name = (name or "yahoo").lower()
    if name == "yahoo":
        return YahooLookupProvider()
    raise ValueError(f"Unknown lookup provider: {name!r}")

"""FundamentalsProvider interface (single-stock company fundamentals).

Company fundamentals are CONTEXT — the company + its valuation, already reflected
in the price — NOT a prediction of the next move (CLAUDE.md honesty rule). Behind
an interface so yfinance can be swapped. Missing fields come back as None ("n/d");
the board never breaks on a gap.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class FundamentalsProvider(Protocol):
    name: str

    def fetch(self, symbol: str) -> dict[str, Any]:
        """Return a structured fundamentals dict for `symbol` (valuation, growth,
        quality, cash, earnings, analysts). Values are None when unavailable.
        Must not raise on missing data; raise only on a hard fetch failure."""
        ...

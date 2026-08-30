"""Fundamentals providers, behind the FundamentalsProvider interface."""
from .base import FundamentalsProvider
from .yfinance_provider import (
    YFinanceFundamentalsProvider,
    parse_fundamentals,
    parse_quarterly,
    valuation_context,
)

__all__ = [
    "FundamentalsProvider",
    "YFinanceFundamentalsProvider",
    "parse_fundamentals",
    "parse_quarterly",
    "valuation_context",
    "build_fundamentals_provider",
]


def build_fundamentals_provider(name: str = "yfinance") -> FundamentalsProvider:
    name = (name or "yfinance").lower()
    if name == "yfinance":
        return YFinanceFundamentalsProvider()
    raise ValueError(f"Unknown fundamentals provider: {name!r}")

"""Fundamentals providers, behind the FundamentalsProvider interface."""
from .base import FundamentalsProvider
from .yfinance_provider import YFinanceFundamentalsProvider, parse_fundamentals

__all__ = [
    "FundamentalsProvider",
    "YFinanceFundamentalsProvider",
    "parse_fundamentals",
    "build_fundamentals_provider",
]


def build_fundamentals_provider(name: str = "yfinance") -> FundamentalsProvider:
    name = (name or "yfinance").lower()
    if name == "yfinance":
        return YFinanceFundamentalsProvider()
    raise ValueError(f"Unknown fundamentals provider: {name!r}")

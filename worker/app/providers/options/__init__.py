"""Options providers, behind the OptionsProvider interface (CLAUDE.md §4)."""
from .base import OptionQuote, OptionsProvider
from .yfinance_provider import YFinanceOptionsProvider

__all__ = [
    "OptionQuote",
    "OptionsProvider",
    "YFinanceOptionsProvider",
    "build_options_provider",
]


def build_options_provider(name: str) -> OptionsProvider:
    name = (name or "yfinance").lower()
    if name == "yfinance":
        return YFinanceOptionsProvider()
    raise ValueError(f"Unknown options provider: {name!r}")

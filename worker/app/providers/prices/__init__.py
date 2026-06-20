from .base import PriceBar, PriceProvider
from .yfinance_provider import YFinancePriceProvider

__all__ = ["PriceBar", "PriceProvider", "YFinancePriceProvider", "build_price_provider"]


def build_price_provider(name: str) -> PriceProvider:
    """Factory: select a PriceProvider implementation by config name."""
    name = (name or "yfinance").lower()
    if name == "yfinance":
        return YFinancePriceProvider()
    raise ValueError(f"Unknown price provider: {name!r}")

"""Positioning providers (COT), behind the PositioningProvider interface."""
from .base import CotReport, PositioningProvider
from .cftc_provider import CftcPositioningProvider

__all__ = [
    "CotReport",
    "PositioningProvider",
    "CftcPositioningProvider",
    "build_positioning_provider",
]


def build_positioning_provider(name: str) -> PositioningProvider:
    name = (name or "cftc").lower()
    if name == "cftc":
        return CftcPositioningProvider()
    raise ValueError(f"Unknown positioning provider: {name!r}")

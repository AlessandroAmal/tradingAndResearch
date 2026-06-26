"""Macro providers, behind the MacroProvider interface (CLAUDE.md §4).

The decision board's single new feed. FRED today; swap by config name only.
"""
from .base import MacroObservation, MacroProvider
from .fred_provider import FredMacroProvider

__all__ = [
    "MacroObservation",
    "MacroProvider",
    "FredMacroProvider",
    "build_macro_provider",
]


def build_macro_provider(name: str) -> MacroProvider:
    """Factory: select a MacroProvider implementation by config name."""
    name = (name or "fred").lower()
    if name == "fred":
        return FredMacroProvider()
    raise ValueError(f"Unknown macro provider: {name!r}")

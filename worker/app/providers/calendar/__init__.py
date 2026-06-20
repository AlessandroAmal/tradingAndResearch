from .base import CalendarEvent, CalendarProvider
from .fmp_provider import FMPCalendarProvider

__all__ = [
    "CalendarEvent",
    "CalendarProvider",
    "FMPCalendarProvider",
    "build_calendar_provider",
]


def build_calendar_provider(name: str) -> CalendarProvider:
    """Factory: select a CalendarProvider implementation by config name."""
    name = (name or "fmp").lower()
    if name == "fmp":
        return FMPCalendarProvider()
    raise ValueError(f"Unknown calendar provider: {name!r}")

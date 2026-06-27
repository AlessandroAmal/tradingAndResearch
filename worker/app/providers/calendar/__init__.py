from typing import TYPE_CHECKING

from .base import CalendarEvent, CalendarProvider
from .fmp_provider import FMPCalendarProvider
from .seeded_provider import SeededCalendarProvider

if TYPE_CHECKING:
    from ...config import AppConfig

__all__ = [
    "CalendarEvent",
    "CalendarProvider",
    "FMPCalendarProvider",
    "SeededCalendarProvider",
    "build_calendar_provider",
]


def build_calendar_provider(name: str, cfg: "AppConfig | None" = None) -> CalendarProvider:
    """Factory: select a CalendarProvider implementation by config name."""
    name = (name or "fmp").lower()
    if name == "fmp":
        return FMPCalendarProvider()
    if name == "seeded":
        seed = dict((cfg.raw.get("calendar", {}) if cfg else {}).get("seed", {}))
        return SeededCalendarProvider(seed)
    raise ValueError(f"Unknown calendar provider: {name!r}")

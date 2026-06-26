"""MacroProvider interface (decision board / FRED feed).

Macro/Fed data (the ONE new feed added for the decision board) sits behind
this interface so FRED (free, today) can be swapped for another macro source
without touching the assembly/storage (CLAUDE.md §4). Providers return a flat
list of dated observations per series; the decision board derives level +
direction itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class MacroObservation:
    series_id: str
    obs_date: date            # observation date
    value: float | None       # FRED uses "." for missing — mapped to None
    source: str


@runtime_checkable
class MacroProvider(Protocol):
    name: str

    def fetch_series(self, series_id: str, *, days: int) -> list[MacroObservation]:
        """Return the last `days` of observations for `series_id`, oldest→newest.

        Implementations must raise on hard failure so the ingestion job can log
        it clearly; missing daily values (weekends/holidays) come back as
        observations with value=None rather than gaps the caller must guess at.
        """
        ...

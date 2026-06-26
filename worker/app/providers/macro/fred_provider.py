"""FRED implementation of MacroProvider.

FRED (Federal Reserve Bank of St. Louis) is free and requires a free API key
(FRED_API_KEY in the worker .env — server-side only, never the browser).

API verified at build time (2026-06): the observations endpoint is
    https://api.stlouisfed.org/fred/series/observations
        ?series_id=<ID>&api_key=<KEY>&file_type=json
            &observation_start=<YYYY-MM-DD>&sort_order=asc
Missing daily values are returned by FRED as the string "." — mapped to None.
Free-tier limit is generous (~120 requests/minute); the decision board reads a
handful of series once per run, well within it.

Series used by the gold decision board (all DAILY, percent / index units):
  - DFII10    10y Treasury real yield (inflation-indexed, constant maturity)
  - T10YIE    10y breakeven inflation rate
  - DTWEXBGS  Nominal Broad U.S. Dollar Index
The set is configurable in config.yaml (decision_board.*.macro / macro.series).
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

import httpx

from ...logging_setup import get_logger
from .base import MacroObservation, MacroProvider

log = get_logger("provider.macro.fred")

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


class FredMacroProvider(MacroProvider):
    name = "fred"

    def __init__(self, api_key: str | None = None, *, timeout: float = 20.0) -> None:
        self._api_key = api_key or os.getenv("FRED_API_KEY")
        self._timeout = timeout

    def fetch_series(self, series_id: str, *, days: int) -> list[MacroObservation]:
        if not self._api_key:
            raise RuntimeError(
                "FRED_API_KEY not set — get a free key at "
                "https://fredaccount.stlouisfed.org/apikeys and add it to the worker .env"
            )
        start = (datetime.now(timezone.utc).date() - timedelta(days=max(days, 1))).isoformat()
        params = {
            "series_id": series_id,
            "api_key": self._api_key,
            "file_type": "json",
            "observation_start": start,
            "sort_order": "asc",
        }
        resp = httpx.get(FRED_BASE, params=params, timeout=self._timeout)
        resp.raise_for_status()
        payload = resp.json()
        rows = payload.get("observations") or []
        out: list[MacroObservation] = []
        for r in rows:
            out.append(
                MacroObservation(
                    series_id=series_id,
                    obs_date=_parse_date(r.get("date")),
                    value=_parse_value(r.get("value")),
                    source=self.name,
                )
            )
        log.debug("FRED %s: %d observations", series_id, len(out))
        return out


def _parse_date(s: str | None) -> date:
    return date.fromisoformat(s[:10]) if s else date.min


def _parse_value(v: object) -> float | None:
    # FRED encodes missing observations as the literal string ".".
    if v is None or v == "." or v == "":
        return None
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None

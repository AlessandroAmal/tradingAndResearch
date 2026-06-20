"""Financial Modeling Prep (FMP) implementation of CalendarProvider.

Free tier requires an API key (FMP_API_KEY) and is rate-limited, so:
  - we request a bounded date window,
  - we wrap HTTP errors with clear messages,
  - if no key is set we raise a clear, actionable error (the calendar
    job then logs it and the dashboard degrades gracefully).

NOTE (CLAUDE.md): verify FMP's current free-tier endpoints/limits before
relying on this in production — terms change. The economic-calendar
endpoint has historically required a paid plan on some tiers; if your
key 403s, switch `providers.calendar` to a manual seed.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

from ...logging_setup import get_logger
from .base import CalendarEvent, CalendarProvider

log = get_logger("provider.calendar.fmp")

FMP_BASE = "https://financialmodelingprep.com/api/v3"
_IMPORTANCE = {0: "low", 1: "low", 2: "medium", 3: "high"}


class FMPCalendarProvider(CalendarProvider):
    name = "fmp"

    def __init__(self, api_key: str | None = None, timeout: float = 20.0) -> None:
        self._api_key = api_key or os.getenv("FMP_API_KEY")
        self._timeout = timeout

    def fetch_events(self, from_date: str, to_date: str) -> list[CalendarEvent]:
        if not self._api_key:
            raise RuntimeError(
                "FMP_API_KEY is not set — cannot fetch the economic calendar. "
                "Set it in .env or switch providers.calendar to a manual seed."
            )
        url = f"{FMP_BASE}/economic_calendar"
        params = {"from": from_date, "to": to_date, "apikey": self._api_key}
        try:
            resp = httpx.get(url, params=params, timeout=self._timeout)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"FMP calendar HTTP {exc.response.status_code} "
                f"({from_date}..{to_date}) — check key/free-tier limits."
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"FMP calendar request failed: {exc}") from exc

        data = resp.json()
        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected FMP calendar payload: {type(data)}")

        events: list[CalendarEvent] = []
        for item in data:
            ts = _parse_ts(item.get("date"))
            if ts is None:
                continue
            events.append(
                CalendarEvent(
                    title=item.get("event") or "Economic event",
                    event_time=ts,
                    category="economic",
                    country=item.get("country"),
                    importance=_IMPORTANCE.get(item.get("impact"), None)
                    or _norm_importance(item.get("impact")),
                    actual=_as_str(item.get("actual")),
                    forecast=_as_str(item.get("estimate")),
                    previous=_as_str(item.get("previous")),
                    symbols=[],
                    source=self.name,
                )
            )
        log.info("FMP returned %d calendar events (%s..%s)", len(events), from_date, to_date)
        return events


def _parse_ts(raw: object) -> datetime | None:
    if not raw or not isinstance(raw, str):
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _norm_importance(raw: object) -> str | None:
    if isinstance(raw, str):
        low = raw.strip().lower()
        if low in {"low", "medium", "high"}:
            return low
    return None


def _as_str(v: object) -> str | None:
    return None if v is None else str(v)

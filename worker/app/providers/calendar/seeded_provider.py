"""Seeded CalendarProvider — recurring macro dates without a paid feed.

Diagnosis: the FMP free tier 403s on /economic_calendar (paid endpoint), so the
`events` table stays empty and the board's "next catalyst" / event-risk factor
goes blind. The recurring macro catalysts (FOMC, ECB, CPI, PCE, NFP, China PMI)
are scheduled far in advance, so we generate them from CONFIG rules (CLAUDE.md
§3: configurable, not hardcoded) behind the existing CalendarProvider interface.

This is read-only reference data — dates, not numbers. `actual/forecast` are
left empty; the calendar's job here is "what's coming and when".

Supported rules (per event in config `calendar.seed.events`):
  - explicit:          {dates: ["YYYY-MM-DD", ...]}
  - nth_weekday:       {n: 1, weekday: 4}   # 1st Friday (Mon=0..Sun=6); n=-1 = last
  - day_of_month:      {day: 12}            # clamped to month length
  - last_business_day: {}                   # last Mon–Fri of the month
Optional per event: time "HH:MM" (UTC, default 12:00), importance, country.
"""
from __future__ import annotations

import calendar as _cal
from datetime import date, datetime, time, timedelta, timezone

from ...logging_setup import get_logger
from .base import CalendarEvent, CalendarProvider

log = get_logger("provider.calendar.seeded")


class SeededCalendarProvider(CalendarProvider):
    name = "seeded"

    def __init__(self, seed_cfg: dict | None = None) -> None:
        self._cfg = dict(seed_cfg or {})

    def fetch_events(self, from_date: str, to_date: str) -> list[CalendarEvent]:
        start = date.fromisoformat(from_date)
        end = date.fromisoformat(to_date)
        specs = self._cfg.get("events", []) or []
        events: list[CalendarEvent] = []
        for spec in specs:
            for d in _dates_for(spec, start, end):
                events.append(_to_event(spec, d))
        events.sort(key=lambda e: e.event_time)
        log.info("Seeded calendar generated %d events (%s..%s)", len(events), from_date, to_date)
        return events


# --- date generation per rule ----------------------------------------
def _dates_for(spec: dict, start: date, end: date) -> list[date]:
    rule = (spec.get("rule") or "explicit").lower()
    if rule == "explicit":
        out = []
        for s in spec.get("dates", []) or []:
            try:
                d = date.fromisoformat(str(s)[:10])
            except ValueError:
                continue
            if start <= d <= end:
                out.append(d)
        return out

    out: list[date] = []
    for y, m in _months_between(start, end):
        d = _date_in_month(rule, spec, y, m)
        if d and start <= d <= end:
            out.append(d)
    return out


def _date_in_month(rule: str, spec: dict, y: int, m: int) -> date | None:
    last_day = _cal.monthrange(y, m)[1]
    if rule == "day_of_month":
        day = min(int(spec.get("day", 1)), last_day)
        return date(y, m, day)
    if rule == "nth_weekday":
        return _nth_weekday(y, m, int(spec.get("n", 1)), int(spec.get("weekday", 0)))
    if rule == "last_business_day":
        d = date(y, m, last_day)
        while d.weekday() >= 5:  # Sat=5, Sun=6
            d -= timedelta(days=1)
        return d
    return None


def _nth_weekday(y: int, m: int, n: int, weekday: int) -> date | None:
    days = [date(y, m, d) for d in range(1, _cal.monthrange(y, m)[1] + 1)
            if date(y, m, d).weekday() == weekday]
    if not days:
        return None
    if n < 0:
        return days[n] if abs(n) <= len(days) else None
    return days[n - 1] if 0 < n <= len(days) else None


def _months_between(start: date, end: date):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m > 12:
            m, y = 1, y + 1


def _to_event(spec: dict, d: date) -> CalendarEvent:
    hh, mm = 12, 0
    raw = spec.get("time")
    if isinstance(raw, str) and ":" in raw:
        try:
            hh, mm = (int(x) for x in raw.split(":")[:2])
        except ValueError:
            pass
    ts = datetime.combine(d, time(hh, mm), tzinfo=timezone.utc)
    return CalendarEvent(
        title=spec.get("title", "Evento"),
        event_time=ts,
        category=spec.get("category", "macro"),
        country=spec.get("country"),
        importance=spec.get("importance", "high"),
        source="seeded",
    )

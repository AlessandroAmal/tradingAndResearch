"""Experiment timing — which entries are due and when each exits. PURE & TESTED.

All times are tz-aware UTC. `eod` ≈ the US cash close (~21:00 UTC); +3d/+5d are
business days. No prices, no I/O, no direction here — just the calendar mechanics.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, time, timedelta, timezone

CLOSE_UTC = time(21, 0)   # ~US market close, good enough for a paper study


def is_key_event(title: str | None, keywords: Sequence[str]) -> bool:
    t = (title or "").lower()
    return any(str(k).lower() in t for k in keywords)


def experiment_key(event_title, event_time, symbol, delay_min, horizon, direction) -> str:
    """Stable idempotency key for one experiment cell."""
    return f"{event_title}|{str(event_time)[:16]}|{symbol}|d{delay_min}|h{horizon}|{direction}"


def parse_dt(s) -> datetime | None:
    if s is None:
        return None
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def due_delays(event_time: datetime, now: datetime,
               delays_min: Sequence[int], grace_min: int) -> list[int]:
    """Delays whose target moment (event_time + delay) has JUST passed — i.e. the
    job is running within [target, target+grace]. Outside that window → skip
    (too early, or too late to open a fair entry)."""
    out: list[int] = []
    for d in delays_min:
        target = event_time + timedelta(minutes=int(d))
        if target <= now <= target + timedelta(minutes=grace_min):
            out.append(int(d))
    return out


def _add_business_days(dt: datetime, n: int) -> datetime:
    d, added = dt, 0
    while added < n:
        d = d + timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d


def exit_time(entry_time: datetime, horizon: str) -> datetime | None:
    """When a position opened at `entry_time` should be closed for `horizon`."""
    if horizon == "eod":
        et = datetime.combine(entry_time.date(), CLOSE_UTC, tzinfo=timezone.utc)
        if entry_time >= et:                       # entered after the close
            et = datetime.combine(_add_business_days(entry_time, 1).date(), CLOSE_UTC, tzinfo=timezone.utc)
        return et
    n = {"3d": 3, "5d": 5}.get(horizon)
    if n is None:
        return None
    return datetime.combine(_add_business_days(entry_time, n).date(), CLOSE_UTC, tzinfo=timezone.utc)


def is_exit_due(exit_time_value, now: datetime) -> bool:
    xt = parse_dt(exit_time_value)
    return xt is not None and now >= xt

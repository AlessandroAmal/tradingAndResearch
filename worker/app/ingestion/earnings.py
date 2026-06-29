"""Earnings dates (yfinance) for single-stock decision boards.

A single stock's dominant catalyst is its quarterly report (a big expected move,
direction unknown). We pull earnings dates from yfinance (free) for instruments
flagged `earnings: true` and (a) add the NEXT one to the calendar `events`, and
(b) use PAST ones for the historical event-behaviour stat.

Read-only, honest about gaps: any failure yields an empty list, and the board
flags "earnings non disponibili" rather than inventing dates. The single
yfinance touch lives in `earnings_dates()` so tests mock just that.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone

from ..logging_setup import get_logger
from ..providers.calendar.base import CalendarEvent

log = get_logger("ingestion.earnings")


def earnings_dates(symbol: str, limit: int = 40) -> list[date]:
    """Past + upcoming earnings dates for `symbol` (sorted). [] on any failure."""
    try:
        import yfinance as yf

        df = yf.Ticker(symbol).get_earnings_dates(limit=limit)
    except Exception as exc:  # noqa: BLE001 — yfinance is unofficial/flaky
        log.warning("earnings_dates(%s) failed: %s", symbol, exc)
        return []
    if df is None or getattr(df, "empty", True):
        return []
    out: set[date] = set()
    for idx in df.index:
        try:
            out.add(idx.date())
        except Exception:  # noqa: BLE001
            continue
    return sorted(out)


def _earnings_instruments(cfg) -> list[tuple[str, str]]:
    db = dict(cfg.raw.get("decision_board", {}) or {})
    return [
        (i["symbol"], i.get("name", i["symbol"]))
        for i in db.get("instruments", []) or []
        if i.get("earnings")
    ]


def upcoming_earnings_events(cfg, today: date | None = None) -> list[CalendarEvent]:
    """Next earnings per flagged instrument, as calendar events (symbol-scoped)."""
    today = today or datetime.now(timezone.utc).date()
    out: list[CalendarEvent] = []
    for symbol, name in _earnings_instruments(cfg):
        upcoming = [d for d in earnings_dates(symbol) if d >= today]
        if not upcoming:
            continue
        d = min(upcoming)
        out.append(CalendarEvent(
            title=f"{name} earnings",
            event_time=datetime.combine(d, time(20, 0), tzinfo=timezone.utc),  # ~US post-close
            category="earnings", country="US", importance="high",
            symbols=[symbol], source="yfinance",
        ))
    return out


def past_earnings(symbol: str, start: date, today: date, limit: int = 60) -> list[date]:
    """Past earnings dates in [start, today) — for the historical event behaviour."""
    return [d for d in earnings_dates(symbol, limit) if start <= d < today]

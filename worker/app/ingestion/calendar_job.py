"""Calendar ingestion job: fetch upcoming events -> storage.

If the provider fails (e.g. FMP free-tier limit / missing key), the job
logs a clear error and returns a failure summary instead of crashing the
scheduler — the dashboard then degrades gracefully (no fresh events).
"""
from __future__ import annotations

from datetime import date, timedelta

from ..config import AppConfig
from ..logging_setup import get_logger
from ..providers.calendar import CalendarProvider
from ..storage import Storage
from .retry import with_retry

log = get_logger("ingestion.calendar")


def run_calendar_ingestion(
    cfg: AppConfig,
    storage: Storage,
    provider: CalendarProvider,
    horizon_days: int = 30,
) -> dict[str, int]:
    today = date.today()
    to = today + timedelta(days=horizon_days)
    from_s, to_s = today.isoformat(), to.isoformat()

    try:
        events = with_retry(
            lambda: provider.fetch_events(from_s, to_s),
            label=f"fetch_events({from_s}..{to_s})",
        )
    except Exception as exc:  # noqa: BLE001
        log.error("Calendar ingestion failed (%s..%s): %s", from_s, to_s, exc)
        return {"ok": 0, "failed": 1}

    rows = [
        {
            "title": e.title,
            "category": e.category,
            "country": e.country,
            "importance": e.importance,
            "event_time": e.event_time.isoformat(),
            "actual": e.actual,
            "forecast": e.forecast,
            "previous": e.previous,
            "symbols": e.symbols,
            "source": e.source,
        }
        for e in events
    ]
    try:
        storage.upsert_events(rows)
    except Exception as exc:  # noqa: BLE001
        log.error("Storing calendar events failed: %s", exc)
        return {"ok": 0, "failed": len(rows)}

    log.info("Calendar ingestion done: %d events", len(rows))
    return {"ok": len(rows), "failed": 0}

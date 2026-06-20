"""APScheduler wiring for the ingestion jobs.

Cron expressions come from config (overridable via env). Jobs are wrapped
so an exception never kills the scheduler — it is logged and the next run
proceeds.
"""
from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import AppConfig
from .ingestion.calendar_job import run_calendar_ingestion
from .ingestion.prices_job import run_prices_ingestion
from .logging_setup import get_logger
from .providers.calendar import build_calendar_provider
from .providers.prices import build_price_provider
from .storage import Storage

log = get_logger("scheduler")


def build_scheduler(cfg: AppConfig, storage: Storage) -> BlockingScheduler:
    sched = BlockingScheduler()
    price_provider = build_price_provider(cfg.providers.get("prices", "yfinance"))
    cal_provider = build_calendar_provider(cfg.providers.get("calendar", "fmp"))

    def _prices() -> None:
        try:
            run_prices_ingestion(cfg, storage, price_provider)
        except Exception as exc:  # noqa: BLE001 — keep scheduler alive
            log.error("Prices job crashed: %s", exc)

    def _calendar() -> None:
        try:
            run_calendar_ingestion(cfg, storage, cal_provider)
        except Exception as exc:  # noqa: BLE001
            log.error("Calendar job crashed: %s", exc)

    sched.add_job(
        _prices,
        CronTrigger.from_crontab(cfg.prices_cron),
        id="prices_ingestion",
        max_instances=1,
        coalesce=True,
    )
    sched.add_job(
        _calendar,
        CronTrigger.from_crontab(cfg.calendar_cron),
        id="calendar_ingestion",
        max_instances=1,
        coalesce=True,
    )
    log.info(
        "Scheduler ready — prices: '%s', calendar: '%s'",
        cfg.prices_cron, cfg.calendar_cron,
    )
    return sched

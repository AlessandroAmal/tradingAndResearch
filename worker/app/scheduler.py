"""APScheduler wiring for the ingestion jobs.

Cron expressions come from config (overridable via env). Jobs are wrapped
so an exception never kills the scheduler — it is logged and the next run
proceeds.
"""
from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .ai import build_ai_client
from .alerts import run_alert_evaluation
from .config import AppConfig
from .ingestion.briefing_job import run_briefing
from .ingestion.calendar_job import run_calendar_ingestion
from .ingestion.figures_job import run_figures_ingestion
from .ingestion.impact_job import run_impact_mapping
from .ingestion.news_job import run_news_ingestion
from .ingestion.options_job import run_options_ingestion
from .ingestion.prices_job import run_prices_ingestion
from .ingestion.tagging_job import run_tagging
from .logging_setup import get_logger
from .providers.calendar import build_calendar_provider
from .providers.figures import build_figure_source
from .notify import build_notifier
from .providers.news import build_news_providers
from .providers.options import build_options_provider
from .providers.prices import build_price_provider
from .storage import Storage

log = get_logger("scheduler")


def build_scheduler(cfg: AppConfig, storage: Storage) -> BlockingScheduler:
    sched = BlockingScheduler()
    price_provider = build_price_provider(cfg.providers.get("prices", "yfinance"))
    cal_provider = build_calendar_provider(cfg.providers.get("calendar", "fmp"))
    news_providers = build_news_providers(cfg)
    figure_source = build_figure_source(cfg)
    options_provider = build_options_provider(cfg.options_provider)
    notifier = build_notifier(cfg)

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

    def _news() -> None:
        try:
            run_news_ingestion(cfg, storage, news_providers)
        except Exception as exc:  # noqa: BLE001
            log.error("News job crashed: %s", exc)

    def _figures() -> None:
        try:
            run_figures_ingestion(cfg, storage, figure_source)
        except Exception as exc:  # noqa: BLE001
            log.error("Figures job crashed: %s", exc)

    def _options() -> None:
        try:
            run_options_ingestion(cfg, storage, options_provider)
        except Exception as exc:  # noqa: BLE001
            log.error("Options job crashed: %s", exc)

    def _alerts() -> None:
        try:
            run_alert_evaluation(cfg, storage, notifier)
        except Exception as exc:  # noqa: BLE001
            log.error("Alerts job crashed: %s", exc)

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
    sched.add_job(
        _news,
        CronTrigger.from_crontab(cfg.news_cron),
        id="news_ingestion",
        max_instances=1,
        coalesce=True,
    )
    sched.add_job(
        _figures,
        CronTrigger.from_crontab(cfg.figures_cron),
        id="figures_ingestion",
        max_instances=1,
        coalesce=True,
    )
    sched.add_job(
        _options,
        CronTrigger.from_crontab(cfg.options_cron),
        id="options_ingestion",
        max_instances=1,
        coalesce=True,
    )
    sched.add_job(
        _alerts,
        CronTrigger.from_crontab(cfg.alerts_cron),
        id="alerts_evaluation",
        max_instances=1,
        coalesce=True,
    )

    # --- AI jobs (only if enabled + key present; degrade gracefully) ---
    ai = None
    if cfg.ai_enabled:
        try:
            ai = build_ai_client()
        except Exception as exc:  # noqa: BLE001 — missing key etc.
            log.warning("AI layer not started (tagging/briefings disabled): %s", exc)

    if ai is not None:
        def _tagging() -> None:
            try:
                run_tagging(cfg, storage, ai)
            except Exception as exc:  # noqa: BLE001
                log.error("Tagging job crashed: %s", exc)

        def _briefing_morning() -> None:
            try:
                run_briefing(cfg, storage, ai, "morning")
            except Exception as exc:  # noqa: BLE001
                log.error("Morning briefing crashed: %s", exc)

        def _briefing_intraday() -> None:
            try:
                run_briefing(cfg, storage, ai, "intraday")
            except Exception as exc:  # noqa: BLE001
                log.error("Intraday briefing crashed: %s", exc)

        def _impact() -> None:
            try:
                run_impact_mapping(cfg, storage, ai)
            except Exception as exc:  # noqa: BLE001
                log.error("Impact mapping job crashed: %s", exc)

        sched.add_job(
            _tagging, CronTrigger.from_crontab(cfg.tagging_cron),
            id="ai_tagging", max_instances=1, coalesce=True,
        )
        sched.add_job(
            _impact, CronTrigger.from_crontab(cfg.impact_cron),
            id="ai_impact", max_instances=1, coalesce=True,
        )
        sched.add_job(
            _briefing_morning, CronTrigger.from_crontab(cfg.briefing_morning_cron),
            id="ai_briefing_morning", max_instances=1, coalesce=True,
        )
        sched.add_job(
            _briefing_intraday, CronTrigger.from_crontab(cfg.briefing_intraday_cron),
            id="ai_briefing_intraday", max_instances=1, coalesce=True,
        )

    log.info(
        "Scheduler ready — prices:'%s' calendar:'%s' news:'%s' ai:%s",
        cfg.prices_cron, cfg.calendar_cron, cfg.news_cron,
        "on" if ai is not None else "off",
    )
    return sched

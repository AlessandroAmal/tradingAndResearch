"""Worker entry point.

Usage (from worker/):
    python -m app.main seed        # seed instruments + holdings from config
    python -m app.main prices      # run price ingestion once
    python -m app.main calendar    # run calendar ingestion once
    python -m app.main run         # start the APScheduler loop (blocking)

Read-only cockpit: there is intentionally NO command that places orders.
"""
from __future__ import annotations

import argparse
import sys

from .config import load_config
from .ingestion.calendar_job import run_calendar_ingestion
from .ingestion.prices_job import run_prices_ingestion
from .ingestion.seed import seed_universe_and_holdings
from .logging_setup import get_logger, setup_logging
from .providers.calendar import build_calendar_provider
from .providers.prices import build_price_provider
from .scheduler import build_scheduler
from .storage import build_storage

log = get_logger("main")


def _cmd_seed(cfg, storage) -> int:
    seed_universe_and_holdings(cfg, storage)
    return 0


def _cmd_prices(cfg, storage) -> int:
    seed_universe_and_holdings(cfg, storage)  # ensure instruments exist
    provider = build_price_provider(cfg.providers.get("prices", "yfinance"))
    res = run_prices_ingestion(cfg, storage, provider)
    return 0 if res["failed"] == 0 else 1


def _cmd_calendar(cfg, storage) -> int:
    provider = build_calendar_provider(cfg.providers.get("calendar", "fmp"))
    res = run_calendar_ingestion(cfg, storage, provider)
    return 0 if res["failed"] == 0 else 1


def _cmd_run(cfg, storage) -> int:
    seed_universe_and_holdings(cfg, storage)
    sched = build_scheduler(cfg, storage)
    log.info("Starting scheduler (Ctrl+C to stop)…")
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")
    return 0


COMMANDS = {
    "seed": _cmd_seed,
    "prices": _cmd_prices,
    "calendar": _cmd_calendar,
    "run": _cmd_run,
}


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description="Trading & Research Command Center worker")
    parser.add_argument("command", choices=sorted(COMMANDS), help="action to run")
    args = parser.parse_args(argv)

    cfg = load_config()
    log.info(
        "Config loaded: %d instruments, account size %s %s",
        len(cfg.universe), cfg.account_size, cfg.base_currency,
    )
    storage = build_storage()
    return COMMANDS[args.command](cfg, storage)


if __name__ == "__main__":
    sys.exit(main())

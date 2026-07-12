"""Worker entry point.

Usage (from worker/):
    python -m app.main seed              # seed instruments + holdings from config
    python -m app.main prices            # run price ingestion once
    python -m app.main calendar          # run calendar ingestion once
    python -m app.main news              # run news ingestion once
    python -m app.main tag               # run AI tagging once
    python -m app.main briefing-morning  # generate a morning briefing once
    python -m app.main briefing-intraday # generate an intraday briefing once
    python -m app.main figures           # run key-figures ingestion once (M4)
    python -m app.main impact            # run AI impact mapping once (M4)
    python -m app.main risk              # print a risk report / breach flags (M6)
    python -m app.main journal-review    # generate an AI trade-journal review (M7)
    python -m app.main options           # fetch chains + IV/Greeks + hedge proposals (M5)
    python -m app.main alerts            # evaluate alert rules + notify (M8)
    python -m app.main macro             # fetch FRED macro series -> macro_series (M9)
    python -m app.main decision          # macro + assemble decision board snapshot (M9)
    python -m app.main api               # serve the local control API (Aggiorna + AI buttons, M9)
    python -m app.main backtest --rule streak_reversion --instrument GC=F   # single backtest
    python -m app.main backtest --scan   # multi-trial scan over universe/params (data-snooping aware)
    python -m app.main run               # start the APScheduler loop (blocking)

Read-only cockpit: there is intentionally NO command that places orders.
"""
from __future__ import annotations

import argparse
import sys

from .ai import build_ai_client
from .alerts import run_alert_evaluation
from .config import load_config
from .ingestion.briefing_job import run_briefing
from .ingestion.calendar_job import run_calendar_ingestion
from .ingestion.figures_job import run_figures_ingestion
from .ingestion.impact_job import run_impact_mapping
from .ingestion.macro_job import run_macro_ingestion
from .ingestion.news_job import run_news_ingestion
from .ingestion.options_job import run_options_ingestion
from .ingestion.prices_job import run_prices_ingestion
from .ingestion.seed import seed_universe_and_holdings
from .ingestion.tagging_job import run_tagging
from .decision import run_decision_board
from .backtest import run_scan, run_single
from .logging_setup import get_logger, setup_logging
from .notify import build_notifier
from .providers.calendar import build_calendar_provider
from .providers.figures import build_figure_source
from .providers.macro import build_macro_provider
from .providers.news import build_news_providers
from .providers.options import build_options_provider
from .providers.prices import build_price_provider
from .journal_review import run_journal_review
from .risk_report import build_risk_report
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
    provider = build_calendar_provider(cfg.providers.get("calendar", "fmp"), cfg)
    res = run_calendar_ingestion(cfg, storage, provider)
    return 0 if res["failed"] == 0 else 1


def _cmd_news(cfg, storage) -> int:
    providers = build_news_providers(cfg)
    res = run_news_ingestion(cfg, storage, providers)
    return 0 if res["failed"] == 0 else 1


def _cmd_tag(cfg, storage) -> int:
    ai = build_ai_client()
    res = run_tagging(cfg, storage, ai)
    return 0 if res["failed"] == 0 else 1


def _cmd_briefing_morning(cfg, storage) -> int:
    ai = build_ai_client()
    res = run_briefing(cfg, storage, ai, "morning")
    return 0 if res["failed"] == 0 else 1


def _cmd_briefing_intraday(cfg, storage) -> int:
    ai = build_ai_client()
    res = run_briefing(cfg, storage, ai, "intraday")
    return 0 if res["failed"] == 0 else 1


def _cmd_figures(cfg, storage) -> int:
    source = build_figure_source(cfg)
    res = run_figures_ingestion(cfg, storage, source)
    return 0 if res["failed"] == 0 else 1


def _cmd_impact(cfg, storage) -> int:
    ai = build_ai_client()
    res = run_impact_mapping(cfg, storage, ai)
    return 0 if res["failed"] == 0 else 1


def _cmd_risk(cfg, storage) -> int:
    build_risk_report(cfg, storage)  # logs the report + breach flags
    return 0


def _cmd_journal_review(cfg, storage) -> int:
    ai = build_ai_client()
    res = run_journal_review(cfg, storage, ai)
    return 0 if res["failed"] == 0 else 1


def _cmd_options(cfg, storage) -> int:
    provider = build_options_provider(cfg.options_provider)
    res = run_options_ingestion(cfg, storage, provider)
    return 0 if res["failed"] == 0 else 1


def _cmd_alerts(cfg, storage) -> int:
    notifier = build_notifier(cfg)
    run_alert_evaluation(cfg, storage, notifier)
    return 0


def _cmd_macro(cfg, storage) -> int:
    provider = build_macro_provider(cfg.macro_provider)
    res = run_macro_ingestion(cfg, storage, provider)
    return 0 if res["failed"] == 0 else 1


def _cmd_decision(cfg, storage) -> int:
    seed_universe_and_holdings(cfg, storage)  # ensure instruments exist
    # Refresh macro first so the board reads current FRED values; non-fatal.
    try:
        run_macro_ingestion(cfg, storage, build_macro_provider(cfg.macro_provider))
    except Exception as exc:  # noqa: BLE001 — board still renders from stored values
        log.warning("Macro refresh failed (board will use last stored values): %s", exc)
    options_provider = build_options_provider(cfg.options_provider)
    ai = None
    if cfg.ai_enabled:
        try:
            ai = build_ai_client()
        except Exception as exc:  # noqa: BLE001 — synthesis optional
            log.warning("AI synthesis off for decision board: %s", exc)
    res = run_decision_board(cfg, storage, options_provider, ai)
    return 0 if res["failed"] == 0 else 1


def _cmd_experiment(cfg, storage) -> int:
    """Run one pass of the controlled event experiment (paper only, never orders)."""
    from .experiment.job import run_event_experiment
    provider = build_price_provider(cfg.providers.get("prices", "yfinance"))
    res = run_event_experiment(cfg, storage, provider)
    log.info("Event experiment: %s", res)
    return 0


def _cmd_backtest(cfg, storage, args) -> int:
    provider = build_price_provider(cfg.providers.get("prices", "yfinance"))
    if args.scan:
        rules = [r.strip() for r in args.rules.split(",")] if args.rules else None
        instruments = [s.strip() for s in args.instruments.split(",")] if args.instruments else None
        result = run_scan(cfg, provider, rules, instruments)
        storage.insert_backtest_run("scan", args.rules, None, None, result)
        d = result.get("deflated", {})
        best = result.get("best", {})
        log.info(
            "SCAN: %d trials | best rule=%s params=%s OOS Sharpe(ann med)=%.2f | "
            "deflated Sharpe=%.3f (n_trials=%d) — best-of-N looks good by chance unless DSR is high",
            result.get("n_trials", 0), best.get("rule"), best.get("params"),
            best.get("oos_sharpe_ann_median", float("nan")),
            (d.get("deflated_sharpe") or float("nan")), d.get("n_trials", 0),
        )
        return 0

    rule = args.rule or "streak_reversion"
    instrument = args.instrument or "GC=F"
    result = run_single(cfg, provider, rule, instrument, _parse_params(args.params))
    storage.insert_backtest_run("single", rule, instrument, result.get("params"), result)
    oos = result["metrics"]["out_of_sample"]
    deg = result["degradation"]["sharpe"]
    log.info(
        "BACKTEST %s on %s | NET OOS: total=%.1f%% Sharpe=%.2f vs B&H total=%.1f%% | "
        "IS->OOS Sharpe %.2f->%.2f | bootstrap p(not>luck)=%.2f p(not>B&H)=%.2f",
        rule, instrument,
        oos["net"]["total_return"] * 100, oos["net"]["sharpe"],
        oos["bh_net"]["total_return"] * 100,
        deg.get("in_sample") or float("nan"), deg.get("out_of_sample") or float("nan"),
        result["bootstrap"]["p_not_better_than_luck"],
        result["bootstrap"]["p_not_better_than_bh"],
    )
    return 0


def _parse_params(raw: str | None) -> dict | None:
    """Parse `--params k=v,k2=v2` into a dict (ints/floats coerced)."""
    if not raw:
        return None
    out: dict = {}
    for pair in raw.split(","):
        if "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        v = v.strip()
        try:
            out[k.strip()] = int(v)
        except ValueError:
            try:
                out[k.strip()] = float(v)
            except ValueError:
                out[k.strip()] = v
    return out or None


def _cmd_api(cfg, storage) -> int:
    # Lazy import so the FastAPI/uvicorn deps are only needed for this command.
    from .api import run as run_api
    return run_api()


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
    "news": _cmd_news,
    "tag": _cmd_tag,
    "briefing-morning": _cmd_briefing_morning,
    "briefing-intraday": _cmd_briefing_intraday,
    "figures": _cmd_figures,
    "impact": _cmd_impact,
    "risk": _cmd_risk,
    "journal-review": _cmd_journal_review,
    "options": _cmd_options,
    "alerts": _cmd_alerts,
    "macro": _cmd_macro,
    "decision": _cmd_decision,
    "experiment": _cmd_experiment,
    "api": _cmd_api,
    "run": _cmd_run,
}


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description="Trading & Research Command Center worker")
    parser.add_argument("command", choices=sorted(list(COMMANDS) + ["backtest"]),
                        help="action to run")
    # Backtest options (used only by the `backtest` command).
    parser.add_argument("--rule", help="backtest rule name (single run)")
    parser.add_argument("--instrument", help="backtest instrument symbol (single run)")
    parser.add_argument("--params", help="rule params, e.g. down_days=5,hold_days=3")
    parser.add_argument("--scan", action="store_true", help="scan universe/params (data-snooping aware)")
    parser.add_argument("--rules", help="comma-separated rules to scan (default: all in config)")
    parser.add_argument("--instruments", help="comma-separated instruments to scan (default: config universe)")
    args = parser.parse_args(argv)

    cfg = load_config()
    log.info(
        "Config loaded: %d instruments, account size %s %s",
        len(cfg.universe), cfg.account_size, cfg.base_currency,
    )
    storage = build_storage()
    if args.command == "backtest":
        return _cmd_backtest(cfg, storage, args)
    return COMMANDS[args.command](cfg, storage)


if __name__ == "__main__":
    sys.exit(main())

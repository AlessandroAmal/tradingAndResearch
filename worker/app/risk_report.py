"""On-demand risk report (M6) — exposes per-position and portfolio FLAGS.

Loads open positions + their latest prices, runs the risk math, and logs a
summary including breaches (stop hit, per-trade risk / heat / max-positions
over limit, deadline near). This is observation only — NO dispatch (Telegram
is M8/Phase 4) and NO order execution.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from .config import AppConfig
from .logging_setup import get_logger
from .risk import evaluate_portfolio, evaluate_position
from .storage import Storage

log = get_logger("risk.report")


def _parse_date(raw: Any) -> date | None:
    if not raw or not isinstance(raw, str):
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def build_risk_report(cfg: AppConfig, storage: Storage) -> dict[str, Any]:
    account = cfg.account_size
    mult_by_symbol = cfg.multiplier_by_symbol
    today = date.today()

    positions = storage.list_positions("open")
    rows: list[dict[str, Any]] = []
    open_risks: list[float | None] = []

    for p in positions:
        symbol = p.get("symbol")
        iid = p.get("instrument_id")
        current = storage.get_latest_close(iid) if iid else None
        multiplier = mult_by_symbol.get(symbol, 1.0)

        pr = evaluate_position(
            side=p.get("side", "long"),
            entry=float(p.get("entry", 0) or 0),
            stop=_num(p.get("stop")),
            target=_num(p.get("target")),
            size=float(p.get("size", 0) or 0),
            current_price=current,
            account_size=account,
            max_risk_per_trade_pct=cfg.max_risk_per_trade_pct,
            multiplier=multiplier,
            deadline=_parse_date(p.get("deadline")),
            today=today,
            deadline_warn_days=cfg.deadline_warn_days,
        )
        open_risks.append(pr.open_risk)
        rows.append({"symbol": symbol, "side": p.get("side"), "risk": pr})

    pf = evaluate_portfolio(
        open_risks=open_risks,
        account_size=account,
        max_portfolio_heat_pct=cfg.max_portfolio_heat_pct,
        max_concurrent_positions=cfg.max_concurrent_positions,
        open_count=len(positions),
    )

    _log_report(rows, pf, cfg)
    return {"positions": rows, "portfolio": pf}


def _num(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _log_report(rows, pf, cfg: AppConfig) -> None:
    log.info(
        "Risk report: %d open positions | heat %.2f%% (limit %.1f%%)%s | positions %d/%d%s",
        pf.open_count,
        pf.heat_pct if pf.heat_pct is not None else 0.0,
        cfg.max_portfolio_heat_pct,
        "  ⚠ HEAT BREACH" if pf.heat_breached else "",
        pf.open_count,
        cfg.max_concurrent_positions,
        "  ⚠ TOO MANY POSITIONS" if pf.positions_breached else "",
    )
    for r in rows:
        pr = r["risk"]
        flags = []
        if pr.stop_breached:
            flags.append("STOP HIT")
        if pr.risk_per_trade_breached:
            flags.append("RISK>LIMIT")
        if pr.deadline_near:
            flags.append(f"DEADLINE {pr.days_to_deadline}d")
        flag_s = ("  ⚠ " + ", ".join(flags)) if flags else ""
        log.info(
            "  %-10s %-5s risk %.1f%% | R %s | P&L %s%s",
            r["symbol"], r["side"],
            pr.open_risk_pct if pr.open_risk_pct is not None else 0.0,
            f"{pr.r_multiple:.1f}" if pr.r_multiple is not None else "-",
            f"{pr.unrealized_pnl:.0f}" if pr.unrealized_pnl is not None else "-",
            flag_s,
        )

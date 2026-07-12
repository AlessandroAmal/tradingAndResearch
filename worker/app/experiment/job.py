"""Event-experiment job — opens/closes paper positions around US data releases.

READ-ONLY: every position is paper=true, experiment=true, broker='EXPERIMENT' —
never an order. Idempotent via a per-cell `experiment_key`, so running every few
minutes only opens each (event × instrument × delay × horizon × direction) once,
and closes each at its horizon. Pure timing/surprise live in `plan`/`surprise`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..config import AppConfig
from ..logging_setup import get_logger
from ..storage import Storage
from .plan import (
    due_delays,
    exit_time,
    experiment_key,
    is_exit_due,
    is_key_event,
    parse_dt,
)
from .surprise import surprise_direction

log = get_logger("experiment.job")

ENTRY_NOTE = (
    "Esperimento evento (paper): MISURA, non un segnale, MAI un ordine. I primi "
    "minuti hanno spread larghi e slippage: i risultati a t+5min sono ottimistici "
    "se non modellati. Un evento non è un campione."
)


def _board_conditions(storage: Storage, symbol: str, cache: dict) -> dict:
    """Snapshot the current lean + implied odds at entry (best-effort, no crash)."""
    if symbol in cache:
        return cache[symbol]
    lean = prob_up = None
    try:
        b = storage.get_decision_board(symbol) or {}
        lean = ((b.get("synthesis") or {}).get("lean") or {}).get("direction")
        hz = [h for h in (b.get("implied") or {}).get("horizons", [])
              if h.get("available") and h.get("prob_up") is not None]
        if hz:
            rep = max(hz, key=lambda h: h.get("days_to_expiry", 0))
            prob_up = rep.get("prob_up")
    except Exception as exc:  # noqa: BLE001
        log.warning("experiment board conditions failed for %s: %s", symbol, exc)
    out = {"lean_direction": lean, "implied_prob_up": prob_up}
    cache[symbol] = out
    return out


def run_event_experiment(cfg: AppConfig, storage: Storage, price_provider,
                         *, now: datetime | None = None) -> dict[str, int]:
    ecfg = cfg.experiment
    if not ecfg.get("enabled", False):
        log.info("Event experiment disabled — skipping.")
        return {"opened": 0, "closed": 0, "skipped": 1}

    now = now or datetime.now(timezone.utc)
    keywords = list(ecfg.get("event_keywords", []))
    instruments = list(ecfg.get("instruments", []))
    delays = list(ecfg.get("delays_min", []))
    horizons = list(ecfg.get("horizons", []))
    directions = list(ecfg.get("directions", ["long", "short"]))
    grace = int(ecfg.get("entry_grace_min", 20))
    lookback = int(ecfg.get("lookback_days", 3))
    spread_bps = float(ecfg.get("spread_bps", 0))

    events = [e for e in storage.list_recent_events(lookback, 200)
              if is_key_event(e.get("title"), keywords)]

    all_positions = storage.list_positions()
    open_keys = {
        (p.get("entry_conditions") or {}).get("experiment_key")
        for p in all_positions if p.get("experiment")
    }
    open_keys.discard(None)

    board_cache: dict[str, dict] = {}
    opened = 0
    for ev in events:
        et = parse_dt(ev.get("event_time"))
        if et is None:
            continue
        due = due_delays(et, now, delays, grace)
        if not due:
            continue
        surprise = surprise_direction(ev.get("actual"), ev.get("forecast"))
        for symbol in instruments:
            cond_base = _board_conditions(storage, symbol, board_cache)
            iid = storage.get_instrument_id(symbol)
            for delay in due:
                for horizon in horizons:
                    for direction in directions:
                        key = experiment_key(ev.get("title"), ev.get("event_time"),
                                              symbol, delay, horizon, direction)
                        if key in open_keys:
                            continue
                        price = price_provider.latest_price(symbol)
                        if not price or price <= 0:
                            continue
                        xt = exit_time(now, horizon)
                        cond = {
                            "experiment": True, "experiment_key": key,
                            "event": ev.get("title"), "event_time": str(ev.get("event_time")),
                            "delay_min": delay, "horizon": horizon, "direction": direction,
                            "surprise": surprise, "entry_price": price,
                            "entry_at": now.isoformat(),
                            "exit_time": xt.isoformat() if xt else None,
                            "spread_bps": spread_bps, **cond_base, "note": ENTRY_NOTE,
                        }
                        storage.insert_position({
                            "instrument_id": iid, "symbol": symbol, "side": direction,
                            "size": 1, "entry": price, "stop": None, "target": None,
                            "broker": "EXPERIMENT", "status": "open",
                            "thesis": f"Esperimento «{ev.get('title')}» t+{delay}m → {horizon} ({direction}).",
                            "paper": True, "experiment": True, "entry_conditions": cond,
                        })
                        open_keys.add(key)
                        opened += 1

    # Close experiment positions that have reached their horizon.
    closed = 0
    for p in all_positions:
        if not p.get("experiment") or p.get("status") != "open":
            continue
        cond = p.get("entry_conditions") or {}
        if not is_exit_due(cond.get("exit_time"), now):
            continue
        price = price_provider.latest_price(p["symbol"])
        if not price or price <= 0:
            continue
        entry = float(p.get("entry") or 0)
        sign = 1.0 if p.get("side") == "long" else -1.0
        pnl = (price - entry) * float(p.get("size") or 1) * sign
        ret = ((price / entry - 1.0) * sign) if entry > 0 else None
        storage.update_position(p["id"], {
            "status": "closed", "closed_at": now.isoformat(), "realized_pnl": pnl,
            "entry_conditions": {**cond, "exit_price": price, "return_pct": ret,
                                 "closed_at": now.isoformat()},
        })
        closed += 1

    log.info("Event experiment: %d opened, %d closed (%d key events)",
             opened, closed, len(events))
    return {"opened": opened, "closed": closed, "events": len(events)}

"""Run the indicator calibration over all decision-board instruments and store it.

Explicit step (CLI `calibrate` / API `/calibrate`) — NOT continuous, to avoid
rolling overfitting. Technical factors are reconstructed causally from prices;
macro drivers use stored FRED history (daily-direction signal, causal). Skew/RR,
COT, event-behaviour, narrative/news and fundamentals are marked "non testabile
con i dati disponibili" (no reliable long causal history in the store) rather than
faked. The deflation test-count spans factors × horizons × instruments.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from .calibration import (
    HORIZONS,
    calibrate_signals,
    causal_technical_signals,
    derive_weights,
)
from .config import AppConfig
from .logging_setup import get_logger
from .storage import Storage

log = get_logger("calibration.runner")

WEIGHT_HORIZON = 5          # the horizon whose IC drives the lean weights
# Lean weight keys that calibration can re-weight (others stay config-driven).
_LEAN_KEYS = {"trend_ma", "rsi"}
# Factors we cannot honestly backtest from the stored data.
_NON_TESTABLE = {
    "skew": "opzioni non storicizzate", "cot": "storico COT non allineato",
    "event_behaviour": "non è un fattore continuo", "news": "storico news insufficiente",
    "fundamentals": "orizzonte anni: non testabile a 1-21g",
}


def _asof_direction_signal(price_dates, macro_rows, supportive_when):
    """Causal macro signal at each price date: +1 if the day's move is supportive
    for the instrument, −1 if adverse, 0 flat. Uses the latest FRED value as-of t."""
    clean = sorted(((str(r.get("obs_date"))[:10], r.get("value")) for r in macro_rows
                    if r.get("value") is not None), key=lambda x: x[0])
    if not clean:
        return [None] * len(price_dates)
    out, i, prev = [], 0, None
    for d in price_dates:
        val = None
        while i < len(clean) and clean[i][0] <= d:
            val = float(clean[i][1]); i += 1
        if val is None:
            out.append(None); continue
        if prev is None:
            out.append(0.0)
        else:
            move = "up" if val > prev else "down" if val < prev else "flat"
            good = "down" if supportive_when == "falling" else "up"
            out.append(1.0 if move == good else -1.0 if move in ("up", "down") else 0.0)
        prev = val
    return out


def run_calibration(cfg: AppConfig, storage: Storage, price_provider, *, progress=None) -> dict:
    db_cfg = dict(cfg.raw.get("decision_board", {}) or {})
    instruments = list(db_cfg.get("instruments", []) or [])
    hist_days = int(db_cfg.get("calibration_history_days", 2600))
    results: dict[str, dict] = {}
    weights: dict[str, dict] = {}
    test_count = 0
    period_start = None

    from .backtest.data import load_history
    total = len(instruments)
    for idx, inst in enumerate(instruments):
        symbol = inst.get("symbol")
        if progress:
            progress(idx, total, symbol)
        try:
            df = load_history(symbol, price_provider, days=hist_days)
        except Exception as exc:  # noqa: BLE001
            log.warning("Calibration: history load failed for %s: %s", symbol, exc)
            continue
        dates = [d.date().isoformat() for d in df.index]
        closes = [float(c) for c in df["close"]]
        if len(closes) < 60:
            continue
        if period_start is None or dates[0] < period_start:
            period_start = dates[0]

        rsi_cfg = dict(inst.get("rsi", {}) or {})
        signals = causal_technical_signals(
            closes, rsi_period=int(rsi_cfg.get("period", 14)),
            overbought=float(rsi_cfg.get("overbought", 70)),
            oversold=float(rsi_cfg.get("oversold", 30)))

        # macro drivers (FRED only; price-source drivers like ^VIX -> use prices)
        for drv in inst.get("macro_drivers", []):
            if (drv.get("source") or "fred").lower() != "fred":
                continue
            rows = storage.get_macro_series(drv.get("id"), 4000)
            signals[f"macro:{drv.get('id')}"] = _asof_direction_signal(
                dates, rows, drv.get("supportive_when"))

        cal = calibrate_signals(signals, closes, horizons=HORIZONS)
        test_count += cal["test_count"]
        # attach non-testable factors as honest placeholders
        for k, why in _NON_TESTABLE.items():
            cal["factors"][k] = {"non_testable": True, "reason": why}
        results[symbol] = cal["factors"]

        dw = derive_weights({k: v for k, v in cal["factors"].items() if isinstance(v, dict) and "non_testable" not in v},
                            horizon=WEIGHT_HORIZON)
        # keep only the lean-weight keys the board actually applies
        weights[symbol] = {k: v for k, v in dw.items() if k in _LEAN_KEYS}

    row = {
        "calibrated_at": datetime.now(timezone.utc).isoformat(),
        "period_start": period_start, "period_end": date.today().isoformat(),
        "horizons": list(HORIZONS), "test_count": test_count,
        "weight_horizon": WEIGHT_HORIZON,
        "results": results, "weights": weights,
    }
    try:
        storage.insert_calibration(row)
        log.info("Calibration stored: %d instruments, %d tests", len(results), test_count)
    except Exception as exc:  # noqa: BLE001 — needs migration 0019
        log.warning("Could not store calibration (apply migration 0019?): %s", exc)
    return {"instruments": len(results), "test_count": test_count}

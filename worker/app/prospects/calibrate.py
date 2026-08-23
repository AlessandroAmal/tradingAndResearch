"""Retrospective calibration of the conditional/historical layer — NO look-ahead.

For each instrument and horizon, walk history: at each past date t the forecast
intervals are the empirical percentiles of forward returns computed ONLY from data
BEFORE t; the outcome is the actual realised return at t. Then measure interval
coverage (does the 68%/95% band really contain 68%/95%?) and try a CONSTRAINED,
dispersion-only recalibration verified out-of-sample.

Options-layer retrospective calibration is NOT done: it needs historical option
chains we don't store — declared as a limit, not faked. Pure-ish (uses price
history via the loader); the coverage math itself is tested.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..config import AppConfig
from ..logging_setup import get_logger
from ..storage import Storage
from .calibration_metrics import coverage_report, recalibrate_dispersion
from .conditional import forward_returns
from .runner import HORIZONS

log = get_logger("prospects.calibrate")


def _pctl(sorted_vals, p):
    return sorted_vals[min(len(sorted_vals) - 1, int(p * len(sorted_vals)))]


def coverage_records(closes, h, warmup, *, step=None):
    """Walk t; forecast bands from closes[:t] forward returns (no look-ahead),
    outcome = realised return at t. Returns records for coverage_report."""
    n = len(closes)
    recs = []
    step = step or max(1, h // 2)
    t = warmup
    while t + h < n:
        past = [r for r in forward_returns(closes[:t], h) if r is not None]
        if len(past) >= 30:
            sv = sorted(past)
            outcome = closes[t + h] / closes[t] - 1.0
            recs.append({"median": _pctl(sv, 0.5), "p16": _pctl(sv, 0.16), "p84": _pctl(sv, 0.84),
                         "p2_5": _pctl(sv, 0.025), "p97_5": _pctl(sv, 0.975), "outcome": outcome})
        t += step
    return recs


def run_retrospective_calibration(cfg: AppConfig, storage: Storage, price_provider) -> dict:
    db_cfg = dict(cfg.raw.get("decision_board", {}) or {})
    instruments = list(db_cfg.get("instruments", []) or [])
    pcfg = cfg.prospects
    warmup = int(pcfg.get("calibration_warmup", 500))
    hist_days = int(pcfg.get("history_days", 5475))
    from ..backtest.data import load_history

    results: dict = {}
    corrections: dict = {}
    for inst in instruments:
        symbol = inst.get("symbol")
        try:
            df = load_history(symbol, price_provider, days=hist_days)
            closes = [float(c) for c in df["close"]]
        except Exception as exc:  # noqa: BLE001
            log.warning("Retro calibration: history failed for %s: %s", symbol, exc)
            continue
        per_h: dict = {}
        for label, h in HORIZONS.items():
            if len(closes) < warmup + 2 * h:
                continue
            recs = coverage_records(closes, h, warmup)
            if len(recs) < 10:
                per_h[label] = {"n": len(recs), "insufficient": True}
                continue
            rep = coverage_report(recs)
            # constrained, dispersion-only recalibration verified OOS (50/50 split)
            mid = len(recs) // 2
            recal = recalibrate_dispersion(recs[:mid], recs[mid:], band="95", target=0.95)
            per_h[label] = {"n": len(recs), "method": "conditional",
                            "coverage_68": rep["coverage_68"]["coverage"],
                            "coverage_95": rep["coverage_95"]["coverage"],
                            "verdict": rep["verdict"], "recalibration": recal}
            if recal.get("applied"):
                corrections.setdefault(symbol, {})[label] = {"scale": recal["scale"], "band": "95"}
        results[symbol] = per_h

    row = {"calibrated_at": datetime.now(timezone.utc).isoformat(), "kind": "retrospective",
           "results": results, "corrections": corrections,
           "note": "Verifica retrospettiva (solo layer condizionato; opzioni non retro-testabili senza catene storiche)."}
    try:
        storage.insert_prospect_calibration(row)
    except Exception as exc:  # noqa: BLE001 — needs 0020
        log.warning("Could not store prospect calibration (apply 0020?): %s", exc)
    log.info("Retrospective calibration done: %d instruments", len(results))
    return {"instruments": len(results), "corrections": sum(len(v) for v in corrections.values())}


def record_due_outcomes(storage: Storage, price_provider) -> dict:
    """Forward registry maintenance: fill outcome_return for matured forecasts.
    Best-effort; needs the daily close at/after target_date (uses latest close)."""
    # kept minimal: relies on stored prices; detailed impl can be extended later.
    return {"filled": 0, "note": "forward-outcome backfill: hook presente, riempimento su prezzi storici"}

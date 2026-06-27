"""Backtest orchestration: single run and multi-trial scan.

Builds the honest result payloads the dashboard renders — always NET, always with
the buy-and-hold comparison, the IS→OOS degradation front and centre, and (for
scans) the trial distribution + deflated Sharpe so a best-of-N is never sold as
an edge.
"""
from __future__ import annotations

import itertools

import numpy as np

from ..config import AppConfig
from ..logging_setup import get_logger
from ..providers.prices import PriceProvider
from .data import load_history
from .engine import _trade_returns, run_backtest
from .metrics import compute_metrics
from .rules import build_signal
from . import safeguards as sg

log = get_logger("backtest.runner")


# --- helpers ---------------------------------------------------------
def _segment(ret: np.ndarray, pos: np.ndarray, a: int, b: int, ppy: int) -> dict:
    seg_ret, seg_pos = ret[a:b], pos[a:b]
    trades = _trade_returns(seg_pos, seg_ret)
    tim = float(np.mean(seg_pos != 0.0)) if len(seg_pos) else 0.0
    return compute_metrics(seg_ret, trades=trades, time_in_market=tim, periods_per_year=ppy)


def _bh(ret_bh: np.ndarray, a: int, b: int, ppy: int) -> dict:
    return compute_metrics(ret_bh[a:b], trades=(), time_in_market=1.0, periods_per_year=ppy)


def _param_combos(grid: dict | None) -> list[dict]:
    if not grid:
        return [{}]
    keys = list(grid)
    return [dict(zip(keys, vals)) for vals in itertools.product(*[grid[k] for k in keys])]


def _downsample(values: np.ndarray, dates: list[str], max_points: int = 800):
    n = len(values)
    if n <= max_points:
        idx = list(range(n))
    else:
        idx = np.linspace(0, n - 1, max_points).astype(int).tolist()
    return [dates[i] for i in idx], [round(float(values[i]), 6) for i in idx], idx


def _run_one(rule: str, params: dict, df, cost_bps: float, is_fraction: float, ppy: int):
    """Run one (rule, params) on one instrument; return engine result + segmented
    NET/GROSS/BH metrics over full / in-sample / out-of-sample."""
    sig = build_signal(rule, df, params)
    res = run_backtest(df, sig, cost_bps=cost_bps, periods_per_year=ppy)
    n = len(res.ret_net)
    k = sg.split_index(n, is_fraction)
    return {
        "res": res, "k": k, "n": n,
        "full_net": _segment(res.ret_net, res.position, 0, n, ppy),
        "full_gross": _segment(res.ret_gross, res.position, 0, n, ppy),
        "full_bh": _bh(res.ret_bh_net, 0, n, ppy),
        "is_net": _segment(res.ret_net, res.position, 0, k, ppy),
        "oos_net": _segment(res.ret_net, res.position, k, n, ppy),
        "is_bh": _bh(res.ret_bh_net, 0, k, ppy),
        "oos_bh": _bh(res.ret_bh_net, k, n, ppy),
    }


# --- single run ------------------------------------------------------
def run_single(cfg: AppConfig, provider: PriceProvider, rule: str, instrument: str,
               params: dict | None = None) -> dict:
    bt = cfg.backtest
    ppy = int(bt.get("periods_per_year", 252))
    cost_bps = float(bt.get("cost_bps", 0.0))
    is_fraction = float(bt.get("is_fraction", 0.6))
    days = int(bt.get("history_days", 5475))

    df = load_history(instrument, provider, days=days,
                      max_age_hours=float(bt.get("cache_max_age_hours", 24)))
    params = params or dict(_rule_defaults(cfg, rule))
    one = _run_one(rule, params, df, cost_bps, is_fraction, ppy)
    res, k, n = one["res"], one["k"], one["n"]

    # Bootstrap on the OOS segment when it's long enough, else the full series.
    if (n - k) >= 60:
        s_ret, b_ret, scope = res.ret_net[k:], res.ret_bh_net[k:], "out_of_sample"
    else:
        s_ret, b_ret, scope = res.ret_net, res.ret_bh_net, "full"
    boot = sg.bootstrap_significance(
        s_ret, b_ret, n_iter=int(bt.get("bootstrap_iter", 1000)),
        block=int(bt.get("bootstrap_block", 5)), seed=int(bt.get("seed", 12345)),
        periods_per_year=ppy,
    )
    boot["scope"] = scope

    dates_net, eq_net, _ = _downsample(res.equity_net, res.dates)
    _, eq_bh, _ = _downsample(res.equity_bh_net, res.dates)
    split_date = res.dates[k] if k < len(res.dates) else None

    return {
        "kind": "single", "rule": rule, "instrument": instrument, "params": params,
        "cost_bps": cost_bps, "n_bars": n, "is_fraction": is_fraction,
        "split_index": k, "split_date": split_date,
        "metrics": {
            "full": {"net": one["full_net"], "gross": one["full_gross"], "bh_net": one["full_bh"]},
            "in_sample": {"net": one["is_net"], "bh_net": one["is_bh"]},
            "out_of_sample": {"net": one["oos_net"], "bh_net": one["oos_bh"]},
        },
        "degradation": {
            "sharpe": sg.degradation(one["is_net"], one["oos_net"], "sharpe"),
            "total_return": sg.degradation(one["is_net"], one["oos_net"], "total_return"),
        },
        "delta_vs_bh_net": {
            "full": one["full_net"]["total_return"] - one["full_bh"]["total_return"],
            "out_of_sample": one["oos_net"]["total_return"] - one["oos_bh"]["total_return"],
        },
        "bootstrap": boot,
        "equity": {"dates": dates_net, "strat_net": eq_net, "bh_net": eq_bh,
                   "split_date": split_date},
        "caveats": sg.CAVEATS,
    }


# --- scan (multiple trials) ------------------------------------------
def run_scan(cfg: AppConfig, provider: PriceProvider, rules: list[str] | None = None,
             instruments: list[str] | None = None) -> dict:
    bt = cfg.backtest
    ppy = int(bt.get("periods_per_year", 252))
    cost_bps = float(bt.get("cost_bps", 0.0))
    is_fraction = float(bt.get("is_fraction", 0.6))
    days = int(bt.get("history_days", 5475))
    max_trials = int(bt.get("max_trials", 200))

    rules = rules or list((bt.get("rules") or {}).keys()) or ["streak_reversion"]
    instruments = instruments or list(bt.get("scan_universe") or cfg.symbols)

    # Load each instrument once (cached).
    frames: dict[str, object] = {}
    for sym in instruments:
        try:
            frames[sym] = load_history(sym, provider, days=days,
                                       max_age_hours=float(bt.get("cache_max_age_hours", 24)))
        except Exception as exc:  # noqa: BLE001 — skip unusable instruments
            log.warning("Scan: skipping %s (%s)", sym, exc)

    # Enumerate trials = rule × param grid.
    trials_def: list[tuple[str, dict]] = []
    for rule in rules:
        grid = (bt.get("rules") or {}).get(rule, {}).get("grid")
        for params in _param_combos(grid):
            trials_def.append((rule, params))
    capped = len(trials_def) > max_trials
    if capped:
        log.warning("Scan capped: %d trials -> %d (max_trials)", len(trials_def), max_trials)
        trials_def = trials_def[:max_trials]

    trials: list[dict] = []
    for rule, params in trials_def:
        per_inst = []
        oos_pp_sharpes = []
        pooled_oos_ret = []
        for sym, df in frames.items():
            try:
                one = _run_one(rule, params, df, cost_bps, is_fraction, ppy)
            except Exception as exc:  # noqa: BLE001
                log.warning("Scan: %s/%s failed (%s)", rule, sym, exc)
                continue
            res, k, n = one["res"], one["k"], one["n"]
            oos_ret = res.ret_net[k:]
            per_inst.append({
                "instrument": sym,
                "oos_sharpe": one["oos_net"]["sharpe"],
                "oos_total_return": one["oos_net"]["total_return"],
                "oos_excess_vs_bh": one["oos_net"]["total_return"] - one["oos_bh"]["total_return"],
            })
            oos_pp_sharpes.append(sg.sharpe_pp(oos_ret))
            pooled_oos_ret.append(oos_ret)
        if not per_inst:
            continue
        score_pp = float(np.median(oos_pp_sharpes))   # per-period, for DSR
        trials.append({
            "rule": rule, "params": params,
            "oos_sharpe_ann_median": float(np.median([p["oos_sharpe"] for p in per_inst])),
            "oos_sharpe_pp_median": score_pp,
            "share_positive_oos": float(np.mean([p["oos_sharpe"] > 0 for p in per_inst])),
            "share_beats_bh_oos": float(np.mean([p["oos_excess_vs_bh"] > 0 for p in per_inst])),
            "per_instrument": per_inst,
            "_pooled_oos": np.concatenate(pooled_oos_ret) if pooled_oos_ret else np.array([]),
        })

    if not trials:
        return {"kind": "scan", "rules": rules, "instruments": list(frames),
                "n_trials": 0, "trials": [], "caveats": sg.CAVEATS,
                "note": "Nessun trial eseguibile (dati insufficienti)."}

    trial_sharpes_pp = [t["oos_sharpe_pp_median"] for t in trials]
    best = max(trials, key=lambda t: t["oos_sharpe_pp_median"])
    deflated = sg.deflated_sharpe(best["_pooled_oos"], trial_sharpes_pp)

    # Strip the heavy arrays before returning/persisting.
    for t in trials:
        t.pop("_pooled_oos", None)
    best_clean = {k: v for k, v in best.items() if k != "_pooled_oos"}
    best_clean["consistency"] = sg.consistency(best["per_instrument"])

    return {
        "kind": "scan", "rules": rules, "instruments": list(frames),
        "n_trials": len(trials), "trials_attempted": len(trials_def), "capped": capped,
        "distribution": {"oos_sharpe_ann": [t["oos_sharpe_ann_median"] for t in trials]},
        "trials": sorted(trials, key=lambda t: t["oos_sharpe_ann_median"], reverse=True),
        "best": best_clean,
        "deflated": deflated,
        "caveats": sg.CAVEATS,
        "note": "Mostrata la DISTRIBUZIONE di tutti i tentativi, non solo il migliore. "
                "Il best-of-N è atteso sembrare buono per caso: vedi lo Sharpe deflazionato.",
    }


def _rule_defaults(cfg: AppConfig, rule: str) -> dict:
    return dict((cfg.backtest.get("rules") or {}).get(rule, {}).get("params", {}))

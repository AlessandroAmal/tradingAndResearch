"""Performance metrics over a per-interval return series — pure & testable.

All metrics are computed identically for GROSS and NET return streams and for
buy-and-hold, so they are directly comparable. Annualisation uses
`periods_per_year` (252 for daily). No metric is presented without its NET
counterpart upstream (CLAUDE.md honesty rule).
"""
from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np


def max_drawdown(equity: np.ndarray) -> float:
    """Largest peak-to-trough drop of an equity curve, as a negative fraction."""
    if len(equity) == 0:
        return 0.0
    peak = np.maximum.accumulate(equity)
    dd = equity / peak - 1.0
    return float(dd.min())


def sharpe(ret: np.ndarray, periods_per_year: int = 252) -> float:
    if len(ret) < 2:
        return 0.0
    sd = float(np.std(ret, ddof=1))
    if sd == 0:
        return 0.0
    return float(np.mean(ret)) / sd * math.sqrt(periods_per_year)


def sortino(ret: np.ndarray, periods_per_year: int = 252) -> float:
    if len(ret) < 2:
        return 0.0
    downside = np.minimum(ret, 0.0)
    dd = math.sqrt(float(np.mean(downside ** 2)))
    if dd == 0:
        return 0.0
    return float(np.mean(ret)) / dd * math.sqrt(periods_per_year)


def cagr(ret: np.ndarray, periods_per_year: int = 252) -> float | None:
    n = len(ret)
    if n == 0:
        return None
    total = float(np.prod(1.0 + ret))
    if total <= 0:
        return -1.0
    years = n / periods_per_year
    if years <= 0:
        return None
    return total ** (1.0 / years) - 1.0


def compute_metrics(
    ret: np.ndarray,
    *,
    trades: Sequence[float] = (),
    time_in_market: float = 0.0,
    periods_per_year: int = 252,
) -> dict:
    ret = np.asarray(ret, dtype=float)
    equity = np.cumprod(1.0 + ret) if len(ret) else np.array([1.0])
    total = float(equity[-1] - 1.0) if len(ret) else 0.0

    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t < 0]
    n_tr = len(trades)
    return {
        "total_return": total,
        "cagr": cagr(ret, periods_per_year),
        "sharpe": sharpe(ret, periods_per_year),
        "sortino": sortino(ret, periods_per_year),
        "max_drawdown": max_drawdown(equity),
        "n_periods": int(len(ret)),
        "n_trades": n_tr,
        "win_rate": (len(wins) / n_tr) if n_tr else None,
        "avg_win": (sum(wins) / len(wins)) if wins else None,
        "avg_loss": (sum(losses) / len(losses)) if losses else None,
        "expectancy": (sum(trades) / n_tr) if n_tr else None,
        "time_in_market": float(time_in_market),
        "ann_return": _annualized_return(ret, periods_per_year),
        "ann_vol": float(np.std(ret, ddof=1) * math.sqrt(periods_per_year)) if len(ret) > 1 else 0.0,
    }


def _annualized_return(ret: np.ndarray, ppy: int) -> float:
    if len(ret) == 0:
        return 0.0
    return float(np.mean(ret) * ppy)

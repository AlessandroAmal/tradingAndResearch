"""Backtest engine — PURE, vectorized, and built to avoid the classic traps.

This is a RESEARCH bench to MEASURE whether a rule has edge — not a signal
generator (CLAUDE.md: read-only, honest about edge). Two non-negotiables live
here in code:

  1. NO LOOK-AHEAD. A rule's `signal[t]` is decided using data only up to the
     CLOSE of bar t. The trade is executed at the OPEN of bar t+1 — never on the
     close of the bar that generated the signal. Concretely, the position held
     over the interval [open t, open t+1] equals `signal[t-1]`.
  2. COSTS ALWAYS DEDUCTED. Every position change pays a configurable cost
     (commission + spread + slippage, in bps) on the traded turnover. We compute
     GROSS and NET; callers must emphasise NET.

The engine also returns the buy-and-hold NET benchmark for the same instrument
on the same basis, so a strategy is never shown without its honest comparison.

Tested in `worker/tests/test_backtest_engine.py` (explicit look-ahead checks).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
    dates: list[str]                 # entry date per interval (df index)
    ret_gross: np.ndarray            # per-interval strategy return (gross)
    ret_net: np.ndarray              # per-interval strategy return (net of costs)
    ret_bh_net: np.ndarray           # buy-and-hold return (net of one entry cost)
    equity_gross: np.ndarray
    equity_net: np.ndarray
    equity_bh_net: np.ndarray
    position: np.ndarray             # position held over each interval
    trades: list[float] = field(default_factory=list)   # per-trade NET returns
    n_trades: int = 0
    time_in_market: float = 0.0
    cost_bps: float = 0.0
    periods_per_year: int = 252


def run_backtest(
    df: pd.DataFrame,
    signal: pd.Series,
    *,
    cost_bps: float = 0.0,
    periods_per_year: int = 252,
) -> BacktestResult:
    """Simulate `signal` on `df` (OHLC, ascending index).

    `signal[t]` ∈ {-1,0,1} is the position DESIRED after close t. It is executed
    at open t+1, i.e. the position over interval t (open t → open t+1) is
    `signal[t-1]`. `cost_bps` is charged per unit of turnover at each change.
    """
    if not {"open", "close"}.issubset(df.columns):
        raise ValueError("df must have 'open' and 'close' columns")
    n = len(df)
    if n < 3:
        raise ValueError("need at least 3 bars to backtest")

    opens = df["open"].to_numpy(dtype=float)
    sig = signal.reindex(df.index).fillna(0.0).to_numpy(dtype=float)

    # Return of holding over interval t = open[t+1]/open[t] - 1 (last is undefined).
    oo = np.zeros(n)
    oo[:-1] = opens[1:] / opens[:-1] - 1.0

    # Position over interval t was decided at close t-1 and entered at open t.
    pos = np.zeros(n)
    pos[1:] = sig[:-1]

    # Turnover (and cost) at the open where the position changes.
    prev = np.zeros(n)
    prev[1:] = pos[:-1]
    turnover = np.abs(pos - prev)
    cost = (cost_bps / 1e4) * turnover

    gross = pos * oo
    net = gross - cost

    # Buy-and-hold: always invested, one entry cost at the start.
    bh = oo.copy()
    bh[0] -= cost_bps / 1e4

    equity_gross = np.cumprod(1.0 + gross)
    equity_net = np.cumprod(1.0 + net)
    equity_bh_net = np.cumprod(1.0 + bh)

    trades = _trade_returns(pos, net)
    return BacktestResult(
        dates=[str(d)[:10] for d in df.index],
        ret_gross=gross, ret_net=net, ret_bh_net=bh,
        equity_gross=equity_gross, equity_net=equity_net, equity_bh_net=equity_bh_net,
        position=pos, trades=trades, n_trades=len(trades),
        time_in_market=float(np.mean(pos != 0.0)),
        cost_bps=cost_bps, periods_per_year=periods_per_year,
    )


def _trade_returns(pos: np.ndarray, net: np.ndarray) -> list[float]:
    """Group consecutive same-direction holding intervals into per-trade NET
    returns (entry & exit costs are already inside `net`)."""
    out: list[float] = []
    n = len(pos)
    i = 0
    while i < n:
        if pos[i] == 0.0:
            i += 1
            continue
        j = i
        comp = 1.0
        while j < n and pos[j] == pos[i]:
            comp *= 1.0 + net[j]
            j += 1
        out.append(comp - 1.0)
        i = j
    return out

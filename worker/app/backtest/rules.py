"""Parametrized technical rules — each returns a 0/1 long-flat signal series.

A rule's `signal[t]` is the position DESIRED after the close of bar t, decided
using ONLY data up to and including close t (rolling indicators are backward by
construction; breakout channels are shifted to exclude the current bar). The
engine executes it at the open of t+1 — so the rules themselves never peek ahead.

Every rule works on any instrument (just an OHLC frame). Defaults and scan grids
live in config (`backtest.rules`).

Tested in `worker/tests/test_backtest_rules.py`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _stateful(entry: pd.Series, exit_: pd.Series) -> pd.Series:
    """Long-flat position: go to 1 on `entry`, back to 0 on `exit_`, hold between.
    Decided bar-by-bar from booleans known at each close (no look-ahead)."""
    pos = np.zeros(len(entry))
    held = 0.0
    e = entry.to_numpy()
    x = exit_.to_numpy()
    for i in range(len(pos)):
        if held == 0.0 and e[i]:
            held = 1.0
        elif held == 1.0 and x[i]:
            held = 0.0
        pos[i] = held
    return pd.Series(pos, index=entry.index)


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    # Wilder smoothing via EWM(alpha=1/period).
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - 100.0 / (1.0 + rs)
    return rsi.fillna(50.0)


# --- rules -----------------------------------------------------------
def ma_crossover(df: pd.DataFrame, fast: int = 50, slow: int = 200,
                 trend_ma: int | None = None) -> pd.Series:
    """Long while fast SMA > slow SMA (optional: also above a long trend SMA)."""
    c = df["close"]
    sig = (c.rolling(fast).mean() > c.rolling(slow).mean())
    if trend_ma:
        sig = sig & (c > c.rolling(trend_ma).mean())
    return sig.astype(float).fillna(0.0)


def rsi_reversion(df: pd.DataFrame, period: int = 14, buy_below: float = 30.0,
                  exit_above: float = 55.0) -> pd.Series:
    """Mean reversion: buy when RSI < buy_below, exit when RSI > exit_above."""
    rsi = _rsi(df["close"], period)
    return _stateful(rsi < buy_below, rsi > exit_above)


def donchian_breakout(df: pd.DataFrame, n: int = 20) -> pd.Series:
    """Channel breakout (support/resistance proxy): long when close exceeds the
    prior-n-day high; exit when it falls below the prior-n-day low. The channel
    is SHIFTED by 1 so the current bar is excluded (no look-ahead)."""
    c = df["close"]
    hi = c.rolling(n).max().shift(1)
    lo = c.rolling(n).min().shift(1)
    return _stateful(c > hi, c < lo)


def streak_reversion(df: pd.DataFrame, down_days: int = 5, hold_days: int = 3) -> pd.Series:
    """The "buy after N consecutive down days, hold M days" mean-reversion rule
    (the '5 down → bounce' idea the user wants to MEASURE — not assume)."""
    c = df["close"].to_numpy()
    n = len(c)
    down = np.zeros(n, dtype=bool)
    down[1:] = c[1:] < c[:-1]
    # trailing run length of down days
    run = np.zeros(n, dtype=int)
    for i in range(1, n):
        run[i] = run[i - 1] + 1 if down[i] else 0
    sig = np.zeros(n)
    for t in range(n):
        if run[t] >= down_days:
            sig[t:t + hold_days] = 1.0   # decided at close t, held the next M intervals
    return pd.Series(sig, index=df.index)


def bollinger_reversion(df: pd.DataFrame, period: int = 20, k: float = 2.0) -> pd.Series:
    """Buy when close pierces the lower Bollinger band, exit at the middle band."""
    c = df["close"]
    mid = c.rolling(period).mean()
    sd = c.rolling(period).std(ddof=0)
    lower = mid - k * sd
    return _stateful(c < lower, c > mid)


REGISTRY = {
    "ma_crossover": ma_crossover,
    "rsi_reversion": rsi_reversion,
    "donchian_breakout": donchian_breakout,
    "streak_reversion": streak_reversion,
    "bollinger_reversion": bollinger_reversion,
}


def build_signal(rule: str, df: pd.DataFrame, params: dict | None = None) -> pd.Series:
    if rule not in REGISTRY:
        raise ValueError(f"Unknown rule {rule!r}. Known: {sorted(REGISTRY)}")
    return REGISTRY[rule](df, **(params or {}))

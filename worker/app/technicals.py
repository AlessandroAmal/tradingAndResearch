"""Technical context for the decision board — PURE, testable, NO I/O.

Descriptive structure only: where price sits relative to its own history. These
are context the user weighs, NOT signals and NEVER predictions (CLAUDE.md §1, §5).
Reuses the audited price math in `app.indicators` (SMA/ATR/distance) and adds
streaks, RSI, range position and distance-to-round-number on top.

Every function returns None / a `flat` / an empty result when there is not
enough data, so the board degrades gracefully rather than raising.

Tested in `worker/tests/test_technicals.py` with known values.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .indicators import (
    average_true_range,
    distance_from_ma_pct,
    simple_moving_average,
)


# --- consecutive streak ----------------------------------------------
@dataclass(frozen=True)
class Streak:
    direction: str   # 'up' | 'down' | 'flat'
    length: int      # number of consecutive same-direction daily moves


def consecutive_streak(closes: Sequence[float]) -> Streak:
    """Current run of consecutive up/down closes ending at the latest bar.

    A "move" compares each close to the previous one. The run stops at the
    first move of the opposite sign (a flat day, change == 0, also stops it).
    `length` counts the moves, e.g. 5 means five consecutive down days.
    """
    if len(closes) < 2:
        return Streak("flat", 0)
    last_diff = closes[-1] - closes[-2]
    if last_diff == 0:
        return Streak("flat", 0)
    direction = "up" if last_diff > 0 else "down"
    length = 0
    for i in range(len(closes) - 1, 0, -1):
        diff = closes[i] - closes[i - 1]
        if (diff > 0 and direction == "up") or (diff < 0 and direction == "down"):
            length += 1
        else:
            break
    return Streak(direction, length)


# --- position vs a moving average ------------------------------------
@dataclass(frozen=True)
class MAPosition:
    period: int
    ma: float | None
    above: bool | None       # None when MA unavailable
    distance_pct: float | None  # +above / -below, percent


def ma_position(closes: Sequence[float], period: int) -> MAPosition:
    ma = simple_moving_average(closes, period)
    if ma is None:
        return MAPosition(period, None, None, None)
    dist = distance_from_ma_pct(closes, period)
    return MAPosition(period, ma, closes[-1] >= ma, dist)


def ma_rising(closes: Sequence[float], period: int, lookback: int = 10) -> bool | None:
    """True if the `period`-SMA is higher now than `lookback` bars ago.

    None when there isn't enough data for both points — the synthesis trend
    factor then treats the slope as unknown (and excludes it).
    """
    if lookback <= 0 or len(closes) <= lookback:
        return None
    cur = simple_moving_average(closes, period)
    prev = simple_moving_average(closes[:-lookback], period)
    if cur is None or prev is None:
        return None
    return cur > prev


# --- RSI (Wilder) ----------------------------------------------------
def rsi(closes: Sequence[float], period: int = 14) -> float | None:
    """Wilder's Relative Strength Index over `period`. None if insufficient data.

    Note: RSI is symmetric and band-agnostic; the over/under thresholds are
    configurable per instrument (gold trends, so 70/30 is too tight — see
    `rsi_zone` callers / config decision_board.*.rsi).
    """
    n = len(closes)
    if period <= 0 or n < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    # Wilder smoothing over the remaining bars.
    for i in range(period + 1, n):
        diff = closes[i] - closes[i - 1]
        gain = diff if diff > 0 else 0.0
        loss = -diff if diff < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def rsi_zone(value: float | None, overbought: float, oversold: float) -> str:
    """Classify an RSI value with CONFIGURABLE thresholds.

    Returns 'overbought' | 'oversold' | 'neutral' | 'n/a'. Thresholds are
    passed in (defaults are tuned per instrument in config — for gold these are
    wider than the textbook 70/30 because a strong trend keeps RSI stretched).
    """
    if value is None:
        return "n/a"
    if value >= overbought:
        return "overbought"
    if value <= oversold:
        return "oversold"
    return "neutral"


# --- position within the last-N-day range ----------------------------
@dataclass(frozen=True)
class RangePosition:
    window: int
    low: float | None
    high: float | None
    pct: float | None        # 0.0 = at range low, 1.0 = at range high


def range_position(closes: Sequence[float], window: int) -> RangePosition:
    if window <= 0 or len(closes) < 2:
        return RangePosition(window, None, None, None)
    w = closes[-window:] if len(closes) >= window else list(closes)
    lo, hi = min(w), max(w)
    last = closes[-1]
    pct = None if hi == lo else (last - lo) / (hi - lo)
    return RangePosition(len(w), lo, hi, pct)


# --- distance to the nearest round number ----------------------------
@dataclass(frozen=True)
class RoundNumber:
    step: float
    nearest: float | None
    distance: float | None
    distance_pct: float | None


def _auto_step(price: float) -> float:
    """A sensible round-number grid for the price magnitude.

    e.g. ~3000 -> 100, ~30 -> 1, ~1.1 -> 0.1. Used when no step is configured.
    """
    if price <= 0:
        return 1.0
    magnitude = 10 ** math.floor(math.log10(price))
    return magnitude / 10.0


def distance_to_round(price: float | None, step: float | None = None) -> RoundNumber:
    if price is None or price <= 0:
        return RoundNumber(step or 0.0, None, None, None)
    s = step if step and step > 0 else _auto_step(price)
    nearest = round(price / s) * s
    distance = abs(price - nearest)
    pct = (distance / price * 100.0) if price else None
    return RoundNumber(s, nearest, distance, pct)


# --- aggregate -------------------------------------------------------
def compute_technicals(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    *,
    ma_periods: Sequence[int] = (20, 50, 200),
    atr_period: int = 14,
    rsi_period: int = 14,
    rsi_overbought: float = 80.0,
    rsi_oversold: float = 40.0,
    range_window: int = 60,
    round_step: float | None = None,
    slope_lookback: int = 10,
) -> dict:
    """Bundle the technical context into a plain dict for the decision board.

    Defaults are gold-tuned (RSI band 80/40, wider than 70/30). All knobs come
    from config so the same module generalises to any instrument.
    """
    last = closes[-1] if closes else None
    streak = consecutive_streak(closes)
    rsi_val = rsi(closes, rsi_period)
    return {
        "last": last,
        "streak": {"direction": streak.direction, "length": streak.length},
        "ma": [
            {
                "period": p,
                "value": (mp := ma_position(closes, p)).ma,
                "above": mp.above,
                "distance_pct": mp.distance_pct,
                "rising": ma_rising(closes, p, slope_lookback),
            }
            for p in ma_periods
        ],
        "atr": average_true_range(highs, lows, closes, atr_period),
        "atr_pct": (
            average_true_range(highs, lows, closes, atr_period) / last * 100.0
            if last and average_true_range(highs, lows, closes, atr_period)
            else None
        ),
        "rsi": {
            "period": rsi_period,
            "value": rsi_val,
            "zone": rsi_zone(rsi_val, rsi_overbought, rsi_oversold),
            "overbought": rsi_overbought,
            "oversold": rsi_oversold,
        },
        "range": {
            "window": (rp := range_position(closes, range_window)).window,
            "low": rp.low,
            "high": rp.high,
            "pct": rp.pct,
        },
        "round_number": {
            "step": (rn := distance_to_round(last, round_step)).step,
            "nearest": rn.nearest,
            "distance": rn.distance,
            "distance_pct": rn.distance_pct,
        },
    }

"""Price indicators: moving averages, ATR, daily change.

Pure functions over OHLC series — easy to unit-test. This is the kind of
math the brief flags as must-be-correct, so it lives here with tests
(`worker/tests/test_indicators.py`) and is reused by later phases.

These functions return None when there is insufficient data rather than
raising, so the dashboard can degrade gracefully.
"""
from __future__ import annotations

from collections.abc import Sequence


def simple_moving_average(closes: Sequence[float], period: int) -> float | None:
    """SMA of the last `period` closes, or None if not enough data."""
    if period <= 0 or len(closes) < period:
        return None
    window = closes[-period:]
    return sum(window) / period


def daily_change(closes: Sequence[float]) -> tuple[float | None, float | None]:
    """Return (absolute change, percent change) between the last two closes.

    Percent is expressed as a percentage (e.g. 1.5 == +1.5%).
    """
    if len(closes) < 2:
        return None, None
    prev, last = closes[-2], closes[-1]
    abs_change = last - prev
    pct = (abs_change / prev * 100.0) if prev else None
    return abs_change, pct


def distance_from_ma_pct(closes: Sequence[float], period: int) -> float | None:
    """Percent distance of the latest close from its `period`-SMA.

    Positive => price above the MA. None if insufficient data.
    """
    ma = simple_moving_average(closes, period)
    if ma is None or not closes or ma == 0:
        return None
    return (closes[-1] - ma) / ma * 100.0


def average_true_range(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> float | None:
    """Wilder's ATR over `period`. None if insufficient data.

    True Range = max(high-low, |high-prev_close|, |low-prev_close|).
    Uses a simple mean of the last `period` TRs (Phase 1 — adequate for
    display; Wilder smoothing can be added later if needed).
    """
    n = len(closes)
    if n < period + 1 or len(highs) != n or len(lows) != n:
        return None
    trs: list[float] = []
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    window = trs[-period:]
    return sum(window) / period

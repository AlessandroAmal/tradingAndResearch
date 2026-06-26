"""Tests for the decision-board technical math (must be correct)."""
import math

from app.technicals import (
    Streak,
    compute_technicals,
    consecutive_streak,
    distance_to_round,
    ma_position,
    range_position,
    rsi,
    rsi_zone,
)


# --- streak ----------------------------------------------------------
def test_streak_down():
    # 5 strictly decreasing closes -> 4 consecutive down MOVES.
    closes = [110, 108, 106, 104, 102]
    s = consecutive_streak(closes)
    assert s == Streak("down", 4)


def test_streak_up_stops_at_reversal():
    closes = [100, 99, 101, 102, 103]  # last three are up moves
    s = consecutive_streak(closes)
    assert s.direction == "up" and s.length == 3


def test_streak_flat_on_unchanged_last():
    assert consecutive_streak([100, 101, 101]) == Streak("flat", 0)
    assert consecutive_streak([100]) == Streak("flat", 0)


# --- MA position -----------------------------------------------------
def test_ma_position_above():
    closes = [90, 95, 100, 105, 110]  # SMA(5)=100, last=110
    mp = ma_position(closes, 5)
    assert mp.ma == 100.0 and mp.above is True
    assert math.isclose(mp.distance_pct, 10.0)


def test_ma_position_insufficient():
    mp = ma_position([1, 2], 5)
    assert mp.ma is None and mp.above is None and mp.distance_pct is None


# --- RSI -------------------------------------------------------------
def test_rsi_all_gains_is_100():
    closes = list(range(1, 20))  # strictly increasing -> RSI 100
    assert rsi(closes, 14) == 100.0


def test_rsi_known_value():
    # Classic Wilder textbook series (first 14 deltas) -> RSI ~ 70.46.
    closes = [
        44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42,
        45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28,
    ]
    val = rsi(closes, 14)
    assert val is not None and math.isclose(val, 70.46, abs_tol=0.3)


def test_rsi_insufficient():
    assert rsi([1, 2, 3], 14) is None


def test_rsi_zone_thresholds_configurable():
    # Gold band 80/40, NOT 70/30: 72 is neutral here.
    assert rsi_zone(72, overbought=80, oversold=40) == "neutral"
    assert rsi_zone(85, overbought=80, oversold=40) == "overbought"
    assert rsi_zone(35, overbought=80, oversold=40) == "oversold"
    assert rsi_zone(None, 80, 40) == "n/a"


# --- range position --------------------------------------------------
def test_range_position_midpoint():
    closes = [10, 20, 30, 15, 20]  # low 10, high 30, last 20 -> 0.5
    rp = range_position(closes, 5)
    assert rp.low == 10 and rp.high == 30 and math.isclose(rp.pct, 0.5)


def test_range_position_flat_range():
    rp = range_position([5, 5, 5], 3)
    assert rp.pct is None  # high == low


# --- round numbers ---------------------------------------------------
def test_distance_to_round_auto_step():
    # ~3000 -> grid step 100; nearest round to 3040 is 3000, distance 40.
    rn = distance_to_round(3040.0)
    assert rn.step == 100.0 and rn.nearest == 3000.0 and rn.distance == 40.0


def test_distance_to_round_explicit_step():
    rn = distance_to_round(2034.0, step=50.0)
    assert rn.nearest == 2050.0 and rn.distance == 16.0


# --- aggregate -------------------------------------------------------
def test_compute_technicals_bundle():
    closes = [float(x) for x in range(100, 140)]  # 40 strictly rising closes
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    out = compute_technicals(highs, lows, closes, ma_periods=(20,), range_window=10)
    assert out["last"] == 139.0
    assert out["streak"]["direction"] == "up"
    assert out["rsi"]["value"] == 100.0
    assert out["ma"][0]["above"] is True
    assert out["range"]["pct"] == 1.0  # at the top of the range
    assert out["atr"] is not None

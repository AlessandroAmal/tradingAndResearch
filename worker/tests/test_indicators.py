"""Tests for the price-indicator math (must be correct)."""
import math

from app.indicators import (
    average_true_range,
    daily_change,
    distance_from_ma_pct,
    simple_moving_average,
)


def test_sma_basic():
    assert simple_moving_average([1, 2, 3, 4, 5], 5) == 3.0
    assert simple_moving_average([10, 20, 30], 2) == 25.0


def test_sma_insufficient_data():
    assert simple_moving_average([1, 2], 5) is None
    assert simple_moving_average([], 1) is None
    assert simple_moving_average([1, 2, 3], 0) is None


def test_daily_change():
    abs_c, pct = daily_change([100.0, 110.0])
    assert abs_c == 10.0
    assert math.isclose(pct, 10.0)


def test_daily_change_negative():
    abs_c, pct = daily_change([200.0, 150.0])
    assert abs_c == -50.0
    assert math.isclose(pct, -25.0)


def test_daily_change_insufficient():
    assert daily_change([100.0]) == (None, None)


def test_distance_from_ma_pct():
    # last close 110, SMA(5)=100 -> +10%
    closes = [90, 95, 100, 105, 110]
    d = distance_from_ma_pct(closes, 5)
    assert d is not None and math.isclose(d, 10.0)


def test_distance_from_ma_insufficient():
    assert distance_from_ma_pct([1, 2], 5) is None


def test_atr_constant_range():
    # Every bar has H-L = 2, no gaps -> ATR = 2.
    highs = [11, 11, 11, 11, 11]
    lows = [9, 9, 9, 9, 9]
    closes = [10, 10, 10, 10, 10]
    atr = average_true_range(highs, lows, closes, period=4)
    assert atr is not None and math.isclose(atr, 2.0)


def test_atr_insufficient_data():
    assert average_true_range([1, 2], [0, 1], [1, 2], period=14) is None

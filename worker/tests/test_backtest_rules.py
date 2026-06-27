"""Rule signals — expected behaviour + no look-ahead within the rule."""
import numpy as np
import pandas as pd

from app.backtest.rules import build_signal


def _df(closes, opens=None):
    idx = pd.date_range("2020-01-01", periods=len(closes), freq="B")
    opens = opens if opens is not None else closes
    return pd.DataFrame({"open": opens, "high": closes, "low": closes, "close": closes}, index=idx)


def test_streak_reversion_fires_after_n_down_and_holds_m():
    # 5 consecutive down days complete at index 5; then hold 3 bars.
    closes = [10, 9, 8, 7, 6, 5, 5.2, 5.4, 5.6, 6.0]
    sig = build_signal("streak_reversion", _df(closes), {"down_days": 5, "hold_days": 3})
    # run reaches 5 at index 5 -> signal 1 at 5,6,7 (decided at close, held next opens).
    assert sig.iloc[5] == 1.0 and sig.iloc[6] == 1.0 and sig.iloc[7] == 1.0
    assert sig.iloc[4] == 0.0          # only 4 down days so far -> no signal
    assert sig.iloc[8] == 0.0          # hold window finished


def test_streak_reversion_no_lookahead_prefix_invariant():
    # The signal at index t must not change if FUTURE bars change.
    base = [10, 9, 8, 7, 6, 5, 7, 8]
    alt = [10, 9, 8, 7, 6, 5, 1, 1]   # same up to index 5, different after
    s1 = build_signal("streak_reversion", _df(base), {"down_days": 5, "hold_days": 1})
    s2 = build_signal("streak_reversion", _df(alt), {"down_days": 5, "hold_days": 1})
    assert list(s1.iloc[:6]) == list(s2.iloc[:6])   # prefix identical -> no peeking


def test_ma_crossover_long_when_fast_above_slow():
    closes = list(range(1, 60))   # strictly rising -> fast MA > slow MA
    sig = build_signal("ma_crossover", _df(closes), {"fast": 5, "slow": 20})
    assert sig.iloc[-1] == 1.0
    assert sig.iloc[3] == 0.0     # warmup (not enough data) -> 0


def test_donchian_channel_excludes_current_bar():
    # New high at the last bar should trigger (close > prior-n max, shifted).
    closes = [10, 11, 12, 11, 10, 13]
    sig = build_signal("donchian_breakout", _df(closes), {"n": 3})
    assert sig.iloc[-1] == 1.0
    # A flat series never breaks out.
    flat = build_signal("donchian_breakout", _df([5, 5, 5, 5, 5, 5]), {"n": 3})
    assert flat.sum() == 0.0

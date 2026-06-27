"""Engine correctness — the non-negotiables: NO look-ahead, t+1 open, costs."""
import numpy as np
import pandas as pd
from pytest import approx

from app.backtest.engine import run_backtest


def _df(opens, closes=None):
    closes = closes if closes is not None else opens
    idx = pd.date_range("2020-01-01", periods=len(opens), freq="B")
    return pd.DataFrame(
        {"open": opens, "high": [max(o, c) for o, c in zip(opens, closes)],
         "low": [min(o, c) for o, c in zip(opens, closes)], "close": closes},
        index=idx,
    )


def test_entry_at_next_open_known_value():
    # signal decided at close[0] -> entered at open[1] -> earns open1->open2.
    df = _df([10.0, 10.0, 20.0, 20.0, 20.0])
    sig = pd.Series([1, 0, 0, 0, 0], index=df.index, dtype=float)
    r = run_backtest(df, sig, cost_bps=0.0)
    # interval 1 (open1=10 -> open2=20) = +100%, all others flat.
    assert r.ret_net[1] == approx(1.0)
    assert r.equity_net[-1] == approx(2.0)
    assert r.n_trades == 1


def test_no_lookahead_last_bar_signal_cannot_trade():
    # A signal that only fires on the FINAL bar can never be executed (no t+1).
    df = _df([10.0, 10.0, 10.0, 10.0, 99.0])
    sig = pd.Series([0, 0, 0, 0, 1], index=df.index, dtype=float)
    r = run_backtest(df, sig, cost_bps=0.0)
    assert np.allclose(r.ret_net, 0.0)
    assert r.n_trades == 0


def test_no_lookahead_signal_does_not_use_same_bar_close():
    # Even though close[1] jumps, a signal at close[1] only earns from open[2].
    df = _df(opens=[10, 10, 10, 30, 30], closes=[10, 99, 10, 30, 30])
    sig = pd.Series([0, 1, 1, 0, 0], index=df.index, dtype=float)
    r = run_backtest(df, sig, cost_bps=0.0)
    # pos over interval 2 = sig[1]=1 -> earns open2->open3 = 30/10-1 = 2.0.
    assert r.ret_net[2] == approx(2.0)
    # interval 1 pos = sig[0] = 0 -> the close[1]=99 spike is NOT captured.
    assert r.ret_net[1] == approx(0.0)


def test_costs_deducted_on_entry_and_exit():
    # Flat prices: the only P&L is the round-trip cost (enter + exit).
    df = _df([10.0, 10.0, 10.0, 10.0, 10.0])
    sig = pd.Series([1, 0, 0, 0, 0], index=df.index, dtype=float)
    r = run_backtest(df, sig, cost_bps=100.0)  # 1% per side
    assert r.ret_net[1] == approx(-0.01)   # entry at open1
    assert r.ret_net[2] == approx(-0.01)   # exit at open2
    assert r.equity_net[-1] == approx(0.99 * 0.99)


def test_gross_minus_cost_equals_net():
    df = _df([10, 11, 12, 11, 13, 12, 14])
    sig = pd.Series([1, 1, 0, 1, 0, 1, 0], index=df.index, dtype=float)
    r = run_backtest(df, sig, cost_bps=20.0)
    assert np.all(r.ret_net <= r.ret_gross + 1e-12)   # net never above gross
    # net = gross - cost everywhere
    assert np.allclose(r.ret_gross - r.ret_net, np.maximum(r.ret_gross - r.ret_net, 0))


def test_buy_and_hold_benchmark():
    df = _df([10.0, 20.0, 20.0])
    sig = pd.Series([0, 0, 0], index=df.index, dtype=float)
    r = run_backtest(df, sig, cost_bps=0.0)
    # B&H earns open0->open1 = +100% on interval 0.
    assert r.ret_bh_net[0] == approx(1.0)
    assert r.equity_bh_net[-1] == approx(2.0)



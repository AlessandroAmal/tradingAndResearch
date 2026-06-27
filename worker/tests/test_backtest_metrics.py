"""Backtest metrics — known values."""
import numpy as np
from pytest import approx

from app.backtest.metrics import cagr, compute_metrics, max_drawdown, sharpe


def test_max_drawdown_known():
    equity = np.array([1.0, 1.5, 0.75, 1.2])  # peak 1.5 -> trough 0.75 = -50%
    assert max_drawdown(equity) == approx(-0.5)


def test_sharpe_zero_when_no_variance():
    assert sharpe(np.array([0.01, 0.01, 0.01])) == 0.0


def test_sharpe_sign_and_scale():
    ret = np.array([0.02, 0.0, 0.02, 0.0])
    assert sharpe(ret) > 0


def test_cagr_doubling_in_one_year():
    r = 2 ** (1 / 252) - 1
    ret = np.full(252, r)            # doubles over exactly one year
    assert cagr(ret) == approx(1.0, abs=1e-6)


def test_total_return_and_trade_stats():
    ret = np.array([0.1, -0.05, 0.1])
    m = compute_metrics(ret, trades=[0.1, -0.05, 0.1], time_in_market=0.5)
    assert m["total_return"] == approx(1.1 * 0.95 * 1.1 - 1.0)
    assert m["n_trades"] == 3
    assert m["win_rate"] == approx(2 / 3)
    assert m["expectancy"] == approx((0.1 - 0.05 + 0.1) / 3)
    assert m["time_in_market"] == 0.5

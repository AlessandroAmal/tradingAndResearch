"""Anti-illusion safeguards — split, degradation, deflated Sharpe, bootstrap."""
import numpy as np
from pytest import approx

from app.backtest import safeguards as sg


def test_split_index():
    assert sg.split_index(10, 0.6) == 6
    assert sg.split_index(10, 0.0) == 1      # clamped to >=1
    assert sg.split_index(10, 1.0) == 9      # clamped to <=n-1


def test_degradation_reports_drop_and_retained():
    d = sg.degradation({"sharpe": 2.0}, {"sharpe": 0.5}, "sharpe")
    assert d["drop"] == approx(1.5)
    assert d["retained_pct"] == approx(25.0)


def test_expected_max_sharpe_grows_with_trials():
    trials_small = [0.0, 0.1, 0.2]
    trials_big = [0.0, 0.1, 0.2] * 20
    assert sg.expected_max_sharpe(trials_big) > sg.expected_max_sharpe(trials_small)


def test_deflated_sharpe_lower_with_more_trials():
    rng = np.random.default_rng(0)
    best = rng.normal(0.001, 0.01, 500)        # a mediocre "winner"
    few = sg.deflated_sharpe(best, [0.0, 0.02, 0.04])
    many = sg.deflated_sharpe(best, [0.0, 0.02, 0.04] * 30)
    # More trials -> higher bar (expected max) -> lower deflated Sharpe.
    assert many["expected_max_sharpe_pp"] > few["expected_max_sharpe_pp"]
    assert many["deflated_sharpe"] <= few["deflated_sharpe"]
    assert 0.0 <= many["deflated_sharpe"] <= 1.0


def test_bootstrap_reproducible_and_bounded():
    rng = np.random.default_rng(1)
    strat = rng.normal(0.0005, 0.01, 300)
    bh = rng.normal(0.0003, 0.012, 300)
    a = sg.bootstrap_significance(strat, bh, n_iter=200, seed=7)
    b = sg.bootstrap_significance(strat, bh, n_iter=200, seed=7)
    assert a == b                              # same seed -> deterministic
    assert len(a["sharpe_ci95"]) == 2 and a["sharpe_ci95"][0] <= a["sharpe_ci95"][1]
    assert 0.0 <= a["p_not_better_than_luck"] <= 1.0
    assert 0.0 <= a["p_not_better_than_bh"] <= 1.0


def test_consistency_aggregation():
    results = [
        {"oos_sharpe": 1.0, "oos_excess_vs_bh": 0.1},
        {"oos_sharpe": -0.5, "oos_excess_vs_bh": -0.2},
        {"oos_sharpe": 0.3, "oos_excess_vs_bh": 0.05},
    ]
    c = sg.consistency(results)
    assert c["n_instruments"] == 3
    assert c["share_positive_oos_sharpe"] == approx(2 / 3)
    assert c["share_beats_buy_hold_oos"] == approx(2 / 3)

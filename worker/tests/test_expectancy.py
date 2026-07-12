"""Expectancy & survival math — measured stats, CIs, risk-of-ruin, Kelly with the
LOWER bound, sample thresholds, process scorecard. No fabricated probability."""
from pytest import approx

from app.expectancy import (
    bootstrap_ci,
    expectancy_stats,
    kelly_adjusted,
    kelly_fraction,
    process_scorecard,
    risk_of_ruin,
    ruin_curve,
    trade_r,
    wilson_ci,
)


def _trades(rs):
    # r -> pnl with a nominal 100 risk per trade (pnl = r*100)
    return [{"r": r, "pnl": r * 100.0} for r in rs]


def test_trade_r_from_pnl_and_risk():
    # entry 100, stop 98 -> risk 2*size*mult; size 1, mult 100 -> risk 200; pnl 600 -> 3R
    assert trade_r(100, 98, 600, 1, 100) == approx(3.0)
    assert trade_r(100, None, 600, 1, 100) is None      # no stop -> no R


def test_wilson_ci_bounds():
    lo, hi = wilson_ci(15, 30)
    assert 0 <= lo < 0.5 < hi <= 1 and lo < hi
    assert wilson_ci(0, 0) is None


def test_bootstrap_ci_is_deterministic_and_brackets_mean():
    vals = [1, -1, 1, -1, 2, -0.5, 1, -1, 1.5, -1]
    ci = bootstrap_ci(vals, seed=1)
    ci2 = bootstrap_ci(vals, seed=1)
    assert ci == ci2                                     # seeded -> reproducible
    mean = sum(vals) / len(vals)
    assert ci[0] <= mean <= ci[1]


def test_expectancy_stats_and_threshold():
    # 6 winners at +2R, 4 losers at -1R -> win rate 0.6, exp_r = (6*2 - 4*1)/10 = 0.8
    trades = _trades([2] * 6 + [-1] * 4)
    s = expectancy_stats(trades)
    assert s["n"] == 10 and s["sufficient"] is False and "RUMORE" in s["note"]
    assert s["win_rate"] == approx(0.6)
    assert s["avg_win_r"] == approx(2.0) and s["avg_loss_r"] == approx(1.0)
    assert s["expectancy_r"] == approx(0.8)
    assert s["expectancy_eur"] == approx(80.0)
    assert s["profit_factor"] == approx((6 * 2) / (4 * 1))   # 3.0
    assert s["win_rate_ci"][0] < 0.6 < s["win_rate_ci"][1]


def test_max_consecutive_losses():
    trades = _trades([1, -1, -1, -1, 1, -1, -1])
    assert expectancy_stats(trades)["max_consecutive_losses"] == 3


def test_risk_of_ruin_monotonic_in_risk_fraction():
    # positive edge; ruin prob should rise as you bet a bigger fraction
    lo = risk_of_ruin(win_rate=0.55, rr=1.0, risk_frac=0.01, n_runs=3000, seed=3)
    hi = risk_of_ruin(win_rate=0.55, rr=1.0, risk_frac=0.05, n_runs=3000, seed=3)
    assert 0 <= lo <= hi <= 1 and hi > lo
    assert risk_of_ruin(win_rate=0.5, rr=0, risk_frac=0.01) is None


def test_ruin_curve_flags_current():
    curve = ruin_curve(win_rate=0.55, rr=1.2, current_frac=0.02, n_runs=1500)
    cur = [c for c in curve if c["current"]]
    assert len(cur) == 1 and cur[0]["risk_frac"] == approx(0.02)


def test_kelly_uses_lower_bound_and_flags_unproven():
    # strong but SMALL sample -> lower CI bound pulls Kelly down; not proven at n<20
    small = expectancy_stats(_trades([2] * 6 + [-1] * 4))          # n=10
    ka = kelly_adjusted(small)
    assert ka["proven"] is False and "non è ancora dimostrato" in ka["note"]
    assert ka["kelly_lower"] < ka["kelly_mean"]                    # uncertainty penalty
    # big sample with real edge -> proven, quarter < half < lower
    big = expectancy_stats(_trades(([2] * 60) + ([-1] * 40)))      # n=100
    kb = kelly_adjusted(big)
    assert kb["proven"] is True and kb["quarter_kelly"] < kb["half_kelly"] <= kb["kelly_lower"]
    assert kelly_fraction(0.6, 2.0) == approx(0.6 - 0.4 / 2.0)


def test_process_scorecard_splits_clean_vs_forced():
    trades = ([{"r": 2, "pnl": 200, "forced": False}] * 5
              + [{"r": -1, "pnl": -100, "forced": True}] * 3)
    sc = process_scorecard(trades)
    assert sc["n"] == 8 and sc["clean"]["n"] == 5 and sc["forced"]["n"] == 3
    assert sc["pct_forced"] == approx(3 / 8)
    assert sc["clean"]["expectancy_r"] == approx(2.0) and sc["forced"]["expectancy_r"] == approx(-1.0)

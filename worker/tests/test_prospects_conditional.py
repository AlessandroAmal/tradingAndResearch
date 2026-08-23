"""Conditional historical layer — forward returns, regimes, effective-n with
overlap, block bootstrap, sample thresholds."""
from pytest import approx

from app.prospects import conditional as cond


def test_forward_returns_no_lookahead():
    closes = [100, 110, 121]      # +10% steps
    fwd = cond.forward_returns(closes, 1)
    assert fwd[0] == approx(0.1) and fwd[1] == approx(0.1) and fwd[2] is None


def test_effective_n_accounts_for_overlap():
    # 5000 daily obs of a 252-day return are ~19 independent windows, not 5000
    assert cond.effective_n(5000, 252) == 19
    assert cond.effective_n(100, 1) == 100
    assert cond.effective_n(10, 20) == 0


def test_tercile_and_direction_regimes():
    vals = list(range(9))        # 0..8
    reg = cond.tercile_regime(vals)
    assert reg[0] == "low" and reg[4] == "mid" and reg[8] == "high"
    d = cond.direction_regime([1, 2, 3, 4, 5, 6], window=2)
    assert d[0] is None and d[2] == "rising"
    assert cond.direction_regime([5, 4, 3, 2], window=1)[-1] == "falling"


def test_conditional_distribution_filters_and_gates():
    # 400 points; driver 'x' alternates low/high; only 'low' rows kept
    closes = [100 * (1.001 ** i) for i in range(400)]
    x = ["low" if i % 2 == 0 else "high" for i in range(400)]
    d = cond.conditional_distribution(closes, 5, {"x": x}, {"x": "low"}, min_effective=5)
    assert d["conditions"] == {"x": "low"}
    assert d["n"] > 0 and d["n_effective"] == d["n"] // 5
    assert "median" in d and d["median_ci68"][0] <= d["median"] <= d["median_ci68"][1]


def test_pair_conditioning_and_insufficient():
    closes = [100 + i for i in range(120)]
    x = ["high"] * 120
    y = ["rising" if i > 100 else "falling" for i in range(120)]
    # both conditions -> only ~last rows, small n -> insufficient
    d = cond.conditional_distribution(closes, 10, {"x": x, "y": y}, {"x": "high", "y": "rising"}, min_effective=5)
    assert d["sufficient"] is False and "insufficiente" in d["note"]


def test_prob_above_below_at_level():
    closes = [100 * (1.01 ** i) for i in range(300)]   # steady up -> most fwd rets > 0
    reg = {"x": ["low"] * 300}
    d = cond.conditional_distribution(closes, 3, reg, {"x": "low"}, min_effective=1, level_ret=0.0)
    assert d["prob_above"] + d["prob_below"] == approx(1.0)
    assert d["prob_above"] > 0.9    # uptrend -> almost always positive at +3d

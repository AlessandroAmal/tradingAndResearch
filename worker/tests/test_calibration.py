"""Indicator calibration — IC/hit-rate without look-ahead, significance, deflation
count, evidence-based weights (contrary zeroed not inverted). Synthetic fixtures."""
from pytest import approx

from app.calibration import (
    calibrate_factor,
    calibrate_signals,
    causal_technical_signals,
    derive_weights,
    forward_returns,
    spearman,
)


def test_spearman_monotonic():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == approx(1.0)
    assert spearman([1, 2, 3, 4], [40, 30, 20, 10]) == approx(-1.0)


def test_forward_returns_no_lookahead():
    closes = [100, 110, 121, 133.1]        # +10% each step
    fwd = forward_returns(closes, 1)
    assert fwd[0] == approx(0.1) and fwd[2] == approx(0.1)
    assert fwd[-1] is None                 # last t+1 out of range -> no look-ahead


def test_calibrate_factor_detects_real_edge_and_null():
    # oscillating returns so the sign varies; signal = sign(next return) -> perfect
    rets = [0.02 if i % 2 == 0 else -0.015 for i in range(200)]
    closes = [100.0]
    for r in rets:
        closes.append(closes[-1] * (1 + r))
    fwd = forward_returns(closes, 1)
    signal = [(1.0 if (r or 0) > 0 else -1.0) if r is not None else None for r in fwd]
    good = calibrate_factor(signal, closes, 1)
    assert good["ic"] is not None and good["ic"] > 0.9 and good["significant"] is True
    assert good["hit_rate"] == approx(1.0)
    # a constant signal has no rank information -> IC None / not significant
    flat = calibrate_factor([0.0] * len(closes), closes, 1)
    assert flat["significant"] is False


def test_calibrate_signals_counts_tests_for_deflation():
    closes = [100 + (i % 5) for i in range(120)]
    sigs = causal_technical_signals(closes)
    res = calibrate_signals(sigs, closes, horizons=(1, 3, 5))
    assert res["test_count"] == len(sigs) * 3       # factors × horizons (deflation)
    assert set(res["factors"]) == set(sigs)


def test_causal_technical_signals_are_present_and_causal():
    closes = [100 + i * 0.5 for i in range(260)]     # steady uptrend
    sig = causal_technical_signals(closes)
    assert set(sig) == {"rsi", "streak", "trend_ma", "ma200_dist"}
    assert sig["trend_ma"][0] is None and sig["trend_ma"][-1] == 1.0   # uptrend -> +1 once MA200 exists
    assert sig["streak"][-1] > 0                                       # rising -> positive streak


def test_derive_weights_significant_contrary_and_null():
    results = {
        "trend_ma": {"5": {"ic": 0.12, "significant": True}},          # aligned edge
        "rsi": {"5": {"ic": -0.10, "significant": True}},              # contrary
        "streak": {"5": {"ic": 0.03, "significant": False}},           # noise
    }
    w = derive_weights(results, horizon=5)
    assert w["trend_ma"]["weight"] == approx(0.12) and w["trend_ma"]["contrary"] is False
    assert w["rsi"]["weight"] == 0.0 and w["rsi"]["contrary"] is True   # zeroed, NOT inverted
    assert w["streak"]["weight"] == 0.0 and "nessun valore" in w["streak"]["reason"]


def test_calibrated_lean_emits_no_directional_probability():
    """Part B safeguard: recomposed weights must NOT introduce a directional prob."""
    import json
    from app.decision.synthesis import confluence_read
    tech = {"ma": [{"period": 200, "above": True, "rising": True}, {"period": 50, "above": True, "rising": True}],
            "rsi": {"value": 82, "zone": "overbought", "overbought": 80, "oversold": 40},
            "streak": {"direction": "up", "length": 3}}
    # calibrated-style weights (evidence-derived): trend_ma weighted, rsi zeroed
    res = confluence_read(drivers=[], technicals=tech, implied=None, next_event=None,
                          weights={"trend_ma": 0.12, "rsi": 0.0})
    assert "prob_up" not in res["lean"] and "probability" not in json.dumps(res["lean"]).lower()
    assert "score" in res["lean"]      # magnitude only, not a probability

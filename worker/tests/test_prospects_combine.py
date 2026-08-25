"""Combined distribution — track-record weights, mixture variance, bounded factor
tilt, OOS adoption. No fabricated directional score (weights are measured)."""
import math

from pytest import approx

from app.prospects import combine as C


def _dist(median, half68):
    return {"median": median, "p16": median - half68, "p84": median + half68}


def test_weights_prefer_lower_brier():
    w = C.component_weights({"options": {"brier": 0.20}, "conditional": {"brier": 0.40}})
    assert w["options"] > w["conditional"]
    assert w["options"] + w["conditional"] == approx(1.0)


def test_weights_fallback_equal_without_track_record():
    w = C.component_weights({"options": {}, "conditional": {}})
    assert w["options"] == approx(0.5) and w["conditional"] == approx(0.5)


def test_combine_moment_match_and_variance_grows_on_disagreement():
    # two components, same sd, DIFFERENT means -> mixture sd > component sd.
    # to_normal treats the 68% half-band as 1 sd, so component sd = 0.05 here.
    comp_sd = 0.05
    comp = {"a": _dist(0.02, 0.05), "b": _dist(-0.02, 0.05)}
    out = C.combine(comp, {"a": 0.5, "b": 0.5})
    assert out["available"] and out["median"] == approx(0.0, abs=1e-9)
    assert out["sd"] > comp_sd            # between-component variance widens it
    assert out["sd"] == approx(math.sqrt(comp_sd ** 2 + 0.02 ** 2), rel=1e-6)
    # agree -> sd ~ component sd
    agree = C.combine({"a": _dist(0.0, 0.05), "b": _dist(0.0, 0.05)}, {"a": 0.5, "b": 0.5})
    assert agree["sd"] == approx(comp_sd, rel=1e-6)


def test_combine_prob_up_and_level_with_width():
    out = C.combine({"opt": _dist(0.0, 0.05)}, {"opt": 1.0}, level_ret=0.05)
    assert out["prob_up"] == approx(0.5, abs=1e-6)      # symmetric around 0
    assert 0 < out["prob_above"] < 0.5                  # +5% is ~1 sd up
    assert out["p16"] < out["median"] < out["p84"]      # width always present


def test_factor_tilt_only_significant_and_bounded():
    factors = [
        {"key": "trend_ma", "ic": 0.03, "significant": True, "contrary": False},  # 0.03*0.5=0.015 < cap
        {"key": "rsi", "ic": -0.10, "significant": True, "contrary": True},    # contrary -> ignored
        {"key": "streak", "ic": 0.30, "significant": False, "contrary": False}, # insignificant -> ignored
    ]
    t = C.factor_tilt(factors, scale=0.5)
    assert t["factors_used"] == ["trend_ma"] and t["shift"] == approx(0.015) and t["capped"] is False
    # cap at ±2%
    big = C.factor_tilt([{"key": "x", "ic": 0.9, "significant": True, "contrary": False}], scale=0.5)
    assert big["shift"] == approx(C.FACTOR_TILT_CAP) and big["capped"] is True


def test_tilt_shifts_mean_not_width():
    base = C.combine({"a": _dist(0.0, 0.05)}, {"a": 1.0})
    tilted = C.combine({"a": _dist(0.0, 0.05)}, {"a": 1.0}, tilt=0.01)
    assert tilted["median"] == approx(base["median"] + 0.01)
    assert tilted["sd"] == approx(base["sd"])           # tilt never touches width


def test_adopt_combined_only_if_beats_oos():
    win = C.adopt_combined(0.20, 0.25, "options")
    assert win["use"] == "combined" and win["validated"] is True
    lose = C.adopt_combined(0.30, 0.25, "options")
    assert lose["use"] == "options" and "NON batte" in lose["reason"]
    unk = C.adopt_combined(None, 0.25, "options")
    assert unk["validated"] is False

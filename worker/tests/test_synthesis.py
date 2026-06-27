"""Tests for the confluence-read synthesis — transparent + honest.

Critical guarantees verified here:
  * factors classified bullish/bearish/neutral from known inputs,
  * weights aggregate into a -100..+100 lean (never a probability),
  * missing data excludes the factor (not guessed),
  * NO directional-probability number is ever produced,
  * the lean↔market divergence message is correct.
"""
import json

import pytest

from app.decision.synthesis import (
    BEARISH,
    BULLISH,
    NEUTRAL,
    classify_macro_state,
    confluence_read,
)


def _drivers(dfii_state, dxy_state, *, dfii_dir="up", dxy_dir="down", t10_value=2.3):
    return [
        {"id": "DFII10", "label": "Tasso reale 10y", "value": 2.1, "direction": dfii_dir,
         "state": dfii_state, "interpretation": "x", "weight": 1.0},
        {"id": "DTWEXBGS", "label": "Dollaro", "value": 120.0, "direction": dxy_dir,
         "state": dxy_state, "interpretation": "y", "weight": 1.0},
        {"id": "T10YIE", "label": "Breakeven", "value": t10_value, "direction": "flat",
         "state": "neutral", "weight": 0.5},
    ]


def _tech(above200=True, rising200=True, above50=True, rising50=True):
    return {
        "ma": [
            {"period": 200, "above": above200, "rising": rising200},
            {"period": 50, "above": above50, "rising": rising50},
        ],
        "rsi": {"value": 82, "zone": "overbought", "overbought": 80, "oversold": 40},
        "streak": {"direction": "down", "length": 5},
        "atr_pct": 1.2,
    }


def _implied(prob_up_long):
    return {"horizons": [
        {"available": True, "days_to_expiry": 2, "prob_up": 0.49, "target_days": 1},
        {"available": True, "days_to_expiry": 30, "prob_up": prob_up_long, "target_days": 30},
    ]}


# --- classification --------------------------------------------------
def test_macro_factor_classification_from_state():
    r = confluence_read(drivers=_drivers("headwind", "tailwind"), technicals=_tech(),
                        implied=_implied(0.5), next_event=None)
    by = {f["key"]: f for f in r["factors"]}
    assert by["macro:DFII10"]["classification"] == BEARISH   # real rate up = headwind = bearish
    assert by["macro:DTWEXBGS"]["classification"] == BULLISH  # dollar down = tailwind = bullish
    assert by["macro:DFII10"]["kind"] == "directional"


def test_trend_factor_bullish_and_bearish():
    up = confluence_read(drivers=[], technicals=_tech(above200=True, rising200=True),
                         implied=None, next_event=None)
    assert next(f for f in up["factors"] if f["key"] == "trend_ma")["classification"] == BULLISH
    down = confluence_read(drivers=[], technicals=_tech(above200=False, rising200=False,
                                                        above50=False, rising50=False),
                           implied=None, next_event=None)
    assert next(f for f in down["factors"] if f["key"] == "trend_ma")["classification"] == BEARISH


def test_context_factors_never_directional():
    r = confluence_read(drivers=[], technicals=_tech(), implied=None,
                        next_event={"title": "FOMC", "event_time": "2026-07-29"})
    by = {f["key"]: f for f in r["factors"]}
    # streak/atr are context (no fabricated direction); event is a caution flag.
    assert by["streak"]["kind"] == "context" and by["streak"]["classification"] == NEUTRAL
    assert by["atr"]["kind"] == "context"
    assert by["event_risk"]["classification"] == "caution"
    # RSI overbought but weight 0 -> stays context-neutral, NOT bearish.
    assert by["rsi"]["kind"] == "context" and by["rsi"]["classification"] == NEUTRAL


def test_rsi_contributes_only_when_weighted():
    r = confluence_read(drivers=[], technicals=_tech(), implied=None, next_event=None,
                        weights={"trend_ma": 0.0, "rsi": 1.0})
    rsi = next(f for f in r["factors"] if f["key"] == "rsi")
    assert rsi["kind"] == "directional" and rsi["classification"] == BEARISH  # overbought


# --- aggregation -----------------------------------------------------
def test_lean_score_weighted_mean():
    # DFII10 bearish (-1, w1), DTWEXBGS bullish (+1, w1), T10YIE neutral (0, w0.5),
    # trend bullish (+1, w1). An included-but-neutral factor still tempers the
    # lean via the denominator: 100*(-1+1+0+1)/3.5 = 28.6 -> leggermente rialzista.
    r = confluence_read(drivers=_drivers("headwind", "tailwind"),
                        technicals=_tech(above200=True, rising200=True),
                        implied=_implied(0.5), next_event=None,
                        weights={"trend_ma": 1.0, "rsi": 0.0})
    assert r["lean"]["score"] == pytest.approx(28.6, abs=0.1)
    assert r["lean"]["direction"] == BULLISH
    assert "rialzista" in r["lean"]["label"]
    assert r["lean"]["contributing_factors"] == 4   # 3 macro (incl. neutral) + trend


def test_lean_neutral_when_balanced():
    r = confluence_read(drivers=_drivers("headwind", "headwind", dxy_dir="up"),
                        technicals=_tech(above200=True, rising200=True),  # trend bullish
                        implied=_implied(0.5), next_event=None,
                        weights={"trend_ma": 1.0})
    # two bearish macro (-1,-1, w1 each) + neutral T10YIE (0, w0.5) + bullish
    # trend (+1, w1) over weight 3.5 = -28.6.
    assert r["lean"]["score"] == pytest.approx(-28.6, abs=0.1)
    assert r["lean"]["direction"] == BEARISH


# --- missing data ----------------------------------------------------
def test_missing_factor_excluded_not_guessed():
    drivers = _drivers("headwind", "tailwind")
    drivers[1]["value"] = None  # DTWEXBGS data missing
    r = confluence_read(drivers=drivers, technicals=_tech(), implied=None, next_event=None,
                        weights={"trend_ma": 1.0})
    assert "macro:DTWEXBGS" in r["excluded"]
    dxy = next(f for f in r["factors"] if f["key"] == "macro:DTWEXBGS")
    assert dxy["included"] is False
    # excluded factor must not count toward the lean denominator:
    # DFII10 bearish (-1,w1) + T10YIE neutral (0,w0.5) + trend bullish (+1,w1)
    # over w2.5 = 0.0 (DTWEXBGS dropped, not guessed).
    assert r["lean"]["score"] == pytest.approx(0.0, abs=0.1)


def test_no_contributing_factors_gives_insufficient():
    r = confluence_read(drivers=[], technicals={"ma": []}, implied=None, next_event=None,
                        weights={"trend_ma": 1.0})
    assert r["lean"]["score"] is None
    assert r["lean"]["label"] == "dati insufficienti"


# --- HONESTY: no directional probability anywhere --------------------
def test_no_directional_probability_number_anywhere():
    r = confluence_read(drivers=_drivers("headwind", "tailwind"), technicals=_tech(),
                        implied=_implied(0.5), next_event=None)
    # The lean must carry no probability-like field.
    assert all("prob" not in k.lower() and "percent" not in k.lower() for k in r["lean"])
    # The ONLY prob_* values allowed in the whole blob live under market (the
    # option-implied odds passed through) — never invented by the synthesis.
    blob = json.dumps({k: v for k, v in r.items() if k != "market"})
    assert "prob_up" not in blob and "prob_down" not in blob
    # The lean disclaimer states explicitly it is not a probability/forecast.
    assert "probabilità" in r["lean"]["disclaimer"].lower()


# --- market divergence ----------------------------------------------
def test_divergence_priced_in_message():
    # Conditions clearly bullish, market ~neutral (prob_up 0.50) -> "priced in".
    r = confluence_read(drivers=_drivers("tailwind", "tailwind", dfii_dir="down"),
                        technicals=_tech(above200=True, rising200=True),
                        implied=_implied(0.50), next_event=None, weights={"trend_ma": 1.0})
    assert r["lean"]["direction"] == BULLISH
    assert r["market"]["direction"] == NEUTRAL
    assert r["divergence"]["level"] == "notable"
    assert "prezzato" in r["divergence"]["message"]


# --- macro level/regime classification -------------------------------
def test_regime_high_but_falling_is_still_headwind():
    # Real yield: supportive when FALLING. High level (90th pct) but ticking
    # down today -> the REGIME (structural headwind) wins, not "favorable".
    r = classify_macro_state("falling", "down", 0.90, high_pct=0.66, low_pct=0.34)
    assert r["classification"] == BEARISH and r["state"] == "headwind"
    assert r["regime"] == "high" and r["move_class"] == BULLISH  # daily move alone looked good


def test_regime_low_level_is_tailwind():
    r = classify_macro_state("falling", "up", 0.10, high_pct=0.66, low_pct=0.34)
    assert r["classification"] == BULLISH and r["state"] == "tailwind"


def test_regime_mid_falls_back_to_daily_move():
    r = classify_macro_state("falling", "down", 0.50, high_pct=0.66, low_pct=0.34)
    # mid regime -> use the move: falling is supportive -> bullish
    assert r["regime"] == "mid" and r["classification"] == BULLISH


def test_use_regime_false_uses_move_only():
    r = classify_macro_state("falling", "down", 0.90, use_regime=False)
    assert r["classification"] == BULLISH  # ignores the high level


def test_divergence_aligned_message():
    r = confluence_read(drivers=_drivers("tailwind", "tailwind", dfii_dir="down"),
                        technicals=_tech(above200=True, rising200=True),
                        implied=_implied(0.70), next_event=None, weights={"trend_ma": 1.0})
    assert r["market"]["direction"] == BULLISH
    assert r["divergence"]["level"] == "aligned"

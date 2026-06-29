"""FX desk signals: risk reversal (25Δ interp + sign), expected move, event
behaviour, COT percentile/parse, and synthesis integration (no directional %)."""
import json
from datetime import date

from pytest import approx

from app.decision import fx_signals as fx
from app.decision.synthesis import BEARISH, BULLISH, NEUTRAL, confluence_read
from app.providers.positioning.cftc_provider import REPORTS, _parse_rows


# --- interpolation + risk reversal -----------------------------------
def test_interp_linear_and_extrapolation_flag():
    y, extra = fx.interp_y([(0.1, 0.12), (0.4, 0.10)], 0.25)
    assert y == approx(0.11) and extra is False
    y2, extra2 = fx.interp_y([(0.1, 0.12), (0.4, 0.10)], 0.05)
    assert extra2 is True   # outside the delta range -> flagged


def test_risk_reversal_sign_put_bias_is_bearish():
    calls = [(0.15, 0.11), (0.25, 0.10), (0.45, 0.095)]
    puts = [(-0.15, 0.13), (-0.25, 0.14), (-0.45, 0.16)]
    rr = fx.risk_reversal(calls, puts)
    assert rr["iv_call25"] == approx(0.10) and rr["iv_put25"] == approx(0.14)
    assert rr["rr"] == approx(0.04)        # put IV richer -> positive RR
    assert rr["reliability"] == "ok"
    assert fx.rr_lean(rr["rr"]) == BEARISH  # put bias -> bearish lean
    assert fx.rr_lean(-0.01) == BULLISH and fx.rr_lean(0.0) == NEUTRAL


def test_risk_reversal_low_reliability_when_sparse():
    rr = fx.risk_reversal([(0.2, 0.1)], [(-0.2, 0.12)])  # <2 points each side
    assert rr["rr"] is None and rr["reliability"] == "low"


# --- expected move on events -----------------------------------------
def test_expected_move_picks_spanning_expiry():
    today = date(2026, 6, 27)
    events = [{"title": "FOMC", "event_time": "2026-07-29"}]
    atm = [{"expiry": "2026-07-03", "days_to_expiry": 6, "atm_iv": 0.08},
           {"expiry": "2026-08-21", "days_to_expiry": 55, "atm_iv": 0.09}]
    out = fx.expected_move_on_events(events, atm, today=today)
    assert len(out) == 1
    # spanning expiry is the 55-day one; move = 0.09*sqrt(55/365)*100
    import math
    assert out[0]["expected_move_pct"] == approx(0.09 * math.sqrt(55 / 365) * 100)
    assert out[0]["expiry"] == "2026-08-21"


# --- historical event behaviour --------------------------------------
def test_event_behaviour_continued_vs_reversed_with_n():
    dates = [f"2020-01-{i:02d}" for i in range(1, 11)]
    closes_list = [100, 100, 110, 111, 112, 120, 118, 117, 116, 115]
    closes = dict(zip(dates, [float(c) for c in closes_list]))
    events = [date(2020, 1, 3), date(2020, 1, 6)]   # index 2 and 5
    res = fx.event_behaviour(dates, closes, events, follow_days=3, min_sample=2)
    assert res["n"] == 2
    # idx2: +10% then up (continued); idx5: +up then down by idx8 (reversed)
    assert res["pct_continued"] == approx(0.5) and res["pct_reversed"] == approx(0.5)
    assert res["status"] == "ok"
    assert res["median_abs_move_pct"] is not None


def test_event_behaviour_insufficient_sample():
    dates = ["2020-01-01", "2020-01-02", "2020-01-03"]
    closes = {d: 100.0 + i for i, d in enumerate(dates)}
    res = fx.event_behaviour(dates, closes, [date(2020, 1, 2)], min_sample=20)
    assert res["status"] == "insufficient" and res["n"] == 1


# --- COT positioning -------------------------------------------------
def test_positioning_state_extremes_and_neutral():
    hist = list(range(1, 11))
    assert fx.positioning_state(hist, 10)["state"] == "crowded_long"
    assert fx.positioning_state(hist, 1)["state"] == "crowded_short"
    mid = fx.positioning_state(hist, 5)
    assert mid["state"] == "neutral" and mid["percentile"] == approx(0.5)
    assert fx.cot_lean("crowded_long") == BEARISH
    assert fx.cot_lean("crowded_short") == BULLISH
    assert fx.cot_lean("neutral") == NEUTRAL


def test_cftc_parse_net_long_minus_short_sorted():
    rows = [
        {"report_date_as_yyyy_mm_dd": "2026-06-23T00:00:00.000",
         "lev_money_positions_long": "1000", "lev_money_positions_short": "400",
         "open_interest_all": "5000"},
        {"report_date_as_yyyy_mm_dd": "2026-06-16T00:00:00.000",
         "lev_money_positions_long": "900", "lev_money_positions_short": "500",
         "open_interest_all": "4800"},
    ]
    parsed = _parse_rows(rows, REPORTS["tff"]["long"], REPORTS["tff"]["short"])
    assert [c.report_date.isoformat() for c in parsed] == ["2026-06-16", "2026-06-23"]  # oldest first
    assert parsed[-1].net == approx(600.0)   # 1000 - 400


# --- synthesis integration -------------------------------------------
def _fx(rr=0.02, reliability="ok", cot_state="crowded_long"):
    return {
        "risk_reversal": [{"target_days": 30, "days_to_expiry": 30, "rr": rr,
                           "reliability": reliability, "percentile": 0.85}],
        "cot": {"state": cot_state, "percentile": 0.95},
        "expected_move_events": [{"event": "FOMC", "event_date": "2026-07-29", "expected_move_pct": 1.2}],
    }


def test_synthesis_includes_fx_factors_and_lean():
    res = confluence_read(drivers=[], technicals={}, implied=None, next_event=None,
                          weights={"skew": 0.5, "cot": 0.5}, fx=_fx())
    by = {f["key"]: f for f in res["factors"]}
    assert by["skew"]["classification"] == BEARISH and by["skew"]["kind"] == "directional"
    assert by["cot"]["classification"] == BEARISH and by["cot"]["kind"] == "directional"
    assert by["expected_move"]["kind"] == "context"
    # both bearish, weighted -> lean bearish; and NO directional probability field.
    assert res["lean"]["direction"] == BEARISH
    assert all("prob" not in k.lower() for k in res["lean"])


def test_low_reliability_skew_is_context_not_directional():
    res = confluence_read(drivers=[], technicals={}, implied=None, next_event=None,
                          weights={"skew": 0.5}, fx=_fx(reliability="low"))
    skew = next(f for f in res["factors"] if f["key"] == "skew")
    assert skew["kind"] == "context"   # unreliable smile must not drive the lean


def test_cot_non_extreme_is_context():
    res = confluence_read(drivers=[], technicals={}, implied=None, next_event=None,
                          weights={"cot": 0.5}, fx=_fx(cot_state="neutral"))
    cot = next(f for f in res["factors"] if f["key"] == "cot")
    assert cot["kind"] == "context" and cot["classification"] == NEUTRAL

"""Quadro completo — all states side by side, NEVER fused into a score, and the
AI input now carries the fundamentals (the honest 'everything together')."""
from app.decision.full_picture import build_full_picture, FIXED_LABEL
from app.providers.fundamentals import valuation_context


FUND = {
    "valuation": {"pe_trailing": 60.0, "pe_forward": 45.0, "ps": 25.0, "pb": 40.0,
                  "context": {"pe": 45.0, "basis": "forward", "band": "cara",
                              "percentile": 0.82, "n": 12, "note": "ctx"}},
    "growth": {"revenue_yoy": 0.55, "earnings_yoy": -0.10},
    "quality": {"net_margin": 0.50, "roe": 1.2, "gross_margin": 0.7, "operating_margin": 0.6},
    "cash": {"free_cash_flow": 2.0e10, "debt_to_equity": 25.0},
    "earnings": {"next_date": "2026-07-10",
                 "surprises": [{"beat": True}, {"beat": True}, {"beat": False}]},
}

SYNTH = {
    "factors": [
        {"key": "macro:DFII10", "classification": "bearish", "kind": "directional", "included": True},
        {"key": "macro:^VIX", "classification": "bullish", "kind": "directional", "included": True},
        {"key": "trend_ma", "classification": "bullish", "kind": "directional", "included": True},
        {"key": "skew", "classification": "bearish", "kind": "directional", "included": True,
         "detail": "RR 25Δ -0.300"},
    ],
    "market": {"direction": "neutral", "prob_up": 0.52, "horizon": 30},
}
TECH = {"ma": [{"period": 200, "above": True}], "rsi": {"value": 61},
        "streak": {"length": 3, "direction": "up"}}


def test_full_picture_has_all_states_no_fusion():
    fp = build_full_picture(FUND, SYNTH, TECH, {}, days_to_next_earnings=11)
    keys = {f["key"] for f in fp["factors"]}
    # every category present, side by side
    assert {"valuation", "growth", "quality", "cash", "earnings_risk",
            "macro", "technical", "skew"} <= keys
    # NO aggregate/score field anywhere -> nothing is summed
    assert "score" not in fp and "total" not in fp and "lean" not in fp
    for f in fp["factors"]:
        assert "score" not in f and "weight" not in f      # no per-factor numeric weight either


def test_full_picture_implied_is_the_only_number_and_is_flagged():
    fp = build_full_picture(FUND, SYNTH, TECH, {}, days_to_next_earnings=11)
    assert fp["implied"]["highlight"] is True
    assert fp["implied"]["prob_up"] == 0.52            # passed through, not invented
    # the fixed honest label is present
    assert fp["label"] == FIXED_LABEL
    assert "NON sono sommati" in fp["label"]


def test_full_picture_states_are_descriptive_not_directional_for_fundamentals():
    fp = build_full_picture(FUND, SYNTH, TECH, {}, days_to_next_earnings=11)
    by = {f["key"]: f for f in fp["factors"]}
    assert by["valuation"]["state"] == "cara" and by["valuation"]["tone"] == "none"
    assert by["growth"]["state"] == "in crescita"            # revenue +55%
    assert by["quality"]["state"] == "alta"                  # net margin 50%
    assert by["cash"]["state"] == "FCF positivo"
    assert by["earnings_risk"]["state"] == "imminente"       # 11 days
    # macro/technical/skew carry a LEAN word (each = lean of its own category)
    assert by["macro"]["state"] in ("rialzista", "ribassista", "neutro")
    assert by["technical"]["state"] == "rialzista"           # bullish trend factor
    assert by["skew"]["state"] == "ribassista"


def test_full_picture_degrades_when_missing():
    fp = build_full_picture(None, {}, {}, {})
    by = {f["key"]: f for f in fp["factors"]}
    assert by["valuation"]["state"] == "n/d"
    assert fp["implied"]["prob_up"] is None


# --- valuation indicator: descriptive, never directional -------------
def test_valuation_context_percentile_from_history():
    hist = [10, 12, 14, 16, 18, 20, 22, 24, 26, 28]   # current 27 is high
    ctx = valuation_context(27.0, 30.0, hist)
    assert ctx["basis"] == "forward" and ctx["pe"] == 27.0
    assert ctx["percentile"] is not None and ctx["band"] == "cara"
    assert ctx["n"] == 10


def test_valuation_context_falls_back_to_band_without_history():
    ctx = valuation_context(8.0, None, None)            # cheap, no history
    assert ctx["percentile"] is None and ctx["band"] == "economica"
    assert ctx["basis"] == "forward"


def test_valuation_context_na_when_no_pe():
    ctx = valuation_context(None, None, None)
    assert ctx["pe"] is None and ctx["band"] == "n/d" and ctx["percentile"] is None

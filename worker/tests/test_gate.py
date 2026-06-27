"""Pre-trade gate — every warning rule with known values, event trigger, point
value, and the journal draft. No external calls."""
from datetime import datetime, timedelta, timezone

from pytest import approx

from app.gate import build_journal_draft, evaluate_gate, imminent_event

NOW = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)

BASE = dict(
    symbol="GC=F", side="long", entry=2000.0, stop=1990.0, target=2030.0,
    size=1.0, multiplier=100, account_size=100_000,
    max_risk_per_trade_pct=1.0, max_portfolio_heat_pct=6.0,
    max_concurrent_positions=8, rr_min=1.5, now=NOW, event_warn_hours=48,
)


def _codes(res):
    return {w["code"] for w in res["warnings"]}


def test_clean_trade_within_rules_has_no_warnings():
    # gold: risk = 10 * 1 * 100 = 1000 = 1% of 100k (== limit, not over); R/R=3.
    res = evaluate_gate(**BASE)
    assert res["metrics"]["risk_amount"] == approx(1000.0)
    assert res["metrics"]["risk_pct"] == approx(1.0)
    assert res["metrics"]["rr"] == approx(3.0)
    assert _codes(res) == set()
    assert res["has_blocking_warnings"] is False


def test_point_value_drives_risk_warning():
    # Same trade treated as ×1 would look tiny; with ×100 a 3-contract trade
    # risks 3% -> over the 1% limit.
    res = evaluate_gate(**{**BASE, "size": 3.0})
    assert res["metrics"]["risk_pct"] == approx(3.0)
    assert "risk_per_trade" in _codes(res)


def test_heat_warning():
    res = evaluate_gate(**{**BASE, "existing_heat_pct": 5.5})  # +1% -> 6.5% > 6%
    assert res["metrics"]["resulting_heat_pct"] == approx(6.5)
    assert "heat" in _codes(res)


def test_concurrent_warning():
    res = evaluate_gate(**{**BASE, "open_count": 8})  # +1 -> 9 > 8
    assert "concurrent" in _codes(res)


def test_rr_below_threshold_warns():
    # target close to entry -> R/R = 5/10 = 0.5 < 1.5
    res = evaluate_gate(**{**BASE, "target": 2005.0})
    assert res["metrics"]["rr"] == approx(0.5)
    assert "rr_low" in _codes(res)


def test_rr_missing_is_info_not_warn():
    res = evaluate_gate(**{**BASE, "target": None})
    codes = {(w["code"], w["severity"]) for w in res["warnings"]}
    assert ("rr_missing", "info") in codes


def test_event_imminent_warns_and_outside_window_does_not():
    fomc = [{"title": "FOMC decision", "event_time": "2026-06-28T18:00:00+00:00",
             "importance": "high"}]
    near = evaluate_gate(**{**BASE, "events": fomc})        # ~30h ahead, within 48h
    assert "event_risk" in _codes(near)
    far = evaluate_gate(**{**BASE, "events": fomc, "event_warn_hours": 12})
    assert "event_risk" not in _codes(far)


def test_event_matches_symbol_scope():
    ev = [{"title": "NVDA earnings", "event_time": "2026-06-28T12:00:00+00:00",
           "importance": "high", "symbols": ["NVDA"]}]
    # Gold trade should NOT be warned by an NVDA-scoped event.
    res = evaluate_gate(**{**BASE, "events": ev})
    assert "event_risk" not in _codes(res)


def test_contrarian_is_info_note():
    res = evaluate_gate(**{**BASE, "alignment": "contrarian", "lean_direction": "bearish"})
    notes = {(w["code"], w["severity"]) for w in res["warnings"]}
    assert ("contrarian", "info") in notes


def test_journal_draft_built_from_trade():
    res = evaluate_gate(**{**BASE, "thesis": "real rates rolling over", "alignment": "aligned"})
    d = res["journal_draft"]
    assert d["symbol"] == "GC=F" and d["entry_price"] == 2000.0
    assert d["stop"] == 1990.0 and d["size"] == 1.0
    assert d["thesis"] == "real rates rolling over"
    assert "allineato" in d["notes"].lower() and d["reviewed"] is False


def test_imminent_event_helper_picks_nearest():
    evs = [
        {"title": "far", "event_time": "2026-06-29T12:00:00+00:00", "importance": "high"},
        {"title": "near", "event_time": "2026-06-27T18:00:00+00:00", "importance": "high"},
        {"title": "low", "event_time": "2026-06-27T13:00:00+00:00", "importance": "low"},
    ]
    e = imminent_event(evs, symbol="GC=F", now=NOW, within_hours=72)
    assert e["title"] == "near"   # nearest HIGH-impact (the low-impact one is ignored)


def test_gate_never_blocks():
    res = evaluate_gate(**{**BASE, "size": 50.0, "existing_heat_pct": 20.0, "open_count": 20})
    assert len(res["warnings"]) >= 3
    assert res["has_blocking_warnings"] is False   # read-only: warns, never blocks
    assert "non" in res["caveat"].lower()

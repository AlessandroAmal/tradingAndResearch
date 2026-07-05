"""Event context for the board — freshness flags, movement attribution, event-risk
banner, dollar note. All pure; external inputs are passed in (mocked)."""
from datetime import date, datetime, timezone

from pytest import approx

from app.decision.attribution import (
    attribute_movement,
    business_days_between,
    dollar_note,
    event_risk_banner,
    macro_freshness,
)

TODAY = date(2026, 7, 6)          # Monday
NOW = datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)


# --- A) macro freshness ----------------------------------------------
def test_business_days_between_skips_weekend():
    assert business_days_between(date(2026, 7, 2), date(2026, 7, 6)) == 2   # Thu->Mon = Fri,Mon


def test_macro_freshness_flags_stale_and_dates():
    drivers = [
        {"id": "DFII10", "label": "Real yield", "as_of": "2026-07-03"},   # Fri -> 1 bday, fresh
        {"id": "DTWEXBGS", "label": "Dollar", "as_of": "2026-06-25"},     # ~7 bdays -> stale
    ]
    out = macro_freshness(drivers, TODAY, stale_after_business_days=2)
    by = {d["id"]: d for d in out["drivers"]}
    assert by["DFII10"]["stale"] is False and by["DFII10"]["as_of_date"] == "2026-07-03"
    assert by["DTWEXBGS"]["stale"] is True
    assert out["any_stale"] is True and "Dollar" in out["stale_labels"]
    assert out["note"] and "ritardati" in out["note"]


def test_macro_freshness_all_recent_no_note():
    out = macro_freshness([{"id": "X", "as_of": "2026-07-06"}], TODAY, 2)
    assert out["any_stale"] is False and out["note"] is None


# --- B) movement attribution -----------------------------------------
def test_attribution_builds_chain_for_dollar_sensitive():
    news = [{"title": "Gold jumps as dollar slips", "url": "http://x", "source": "Reuters"}]
    events = [{"title": "US Nonfarm Payrolls", "event_time": "2026-07-03T12:30", "importance": "high"}]
    drivers = [{"id": "DTWEXBGS", "label": "Dollaro", "direction": "down", "interpretation": "dollaro giù = supporto"}]
    out = attribute_movement(instrument_name="Gold", recent_return_pct=1.8,
                             news=news, past_events=events, drivers=drivers,
                             dollar_sensitivity="inverse")
    assert out["attributed"] is True and out["note"] is None
    assert out["chain"] is not None
    assert "Payrolls" in out["chain"][0] and "dollaro giù" in out["chain"][2]
    assert "rialzista" in out["chain"][3]      # dollar down + inverse -> bullish context for gold
    assert "non prevede" in out["label"]
    kinds = {i["kind"] for i in out["items"]}
    assert {"event", "macro", "news"} <= kinds


def test_attribution_not_attributed_when_empty():
    out = attribute_movement(instrument_name="Gold", recent_return_pct=1.2,
                             news=[], past_events=[], drivers=[], dollar_sensitivity="inverse")
    assert out["attributed"] is False and "non attribuito" in out["note"]
    assert out["chain"] is None


def test_attribution_no_chain_without_dollar_move():
    # macro event but the dollar driver is flat -> no causal chain, still lists items
    out = attribute_movement(instrument_name="Gold", recent_return_pct=0.5,
                             news=[], past_events=[{"title": "US CPI", "event_time": "2026-07-04T12:00", "importance": "high"}],
                             drivers=[{"id": "DTWEXBGS", "direction": "flat"}],
                             dollar_sensitivity="inverse")
    assert out["chain"] is None and out["attributed"] is True


# --- C) event-risk banner --------------------------------------------
IMPLIED = {"horizons": [
    {"available": True, "days_to_expiry": 1, "expected_move_pct": 0.8},
    {"available": True, "days_to_expiry": 3, "expected_move_pct": 1.5},
]}


def test_event_risk_within_window_uses_expected_move():
    events = [{"title": "FOMC decision", "event_time": "2026-07-08T18:00:00+00:00", "importance": "high"}]
    b = event_risk_banner(events, IMPLIED, symbol="GC=F", now=NOW, within_hours=72)
    assert b and b["title"] == "FOMC decision"
    assert 0 < b["hours_to"] <= 72
    assert b["expected_move_pct"] == approx(1.5)   # ~2.25 days out -> closest to the 3d tenor


def test_event_risk_outside_window_is_none():
    events = [{"title": "FOMC decision", "event_time": "2026-07-12T18:00:00+00:00", "importance": "high"}]
    assert event_risk_banner(events, IMPLIED, symbol="GC=F", now=NOW, within_hours=72) is None


def test_event_risk_respects_symbol_scope():
    events = [{"title": "NVDA earnings", "event_time": "2026-07-07T20:00:00+00:00",
               "importance": "high", "symbols": ["NVDA"]}]
    assert event_risk_banner(events, IMPLIED, symbol="GC=F", now=NOW, within_hours=72) is None


# --- D) dollar note --------------------------------------------------
def test_dollar_note_inverse_favorable_when_dollar_down():
    n = dollar_note([{"id": "DTWEXBGS", "value": 120.0, "direction": "down"}], "inverse")
    assert n and n["context"] == "favorevole" and n["dollar_direction"] == "down"
    assert "INSIEME" in n["text"]


def test_dollar_note_none_when_flat_or_not_sensitive():
    assert dollar_note([{"id": "DTWEXBGS", "value": 120.0, "direction": "flat"}], "inverse") is None
    assert dollar_note([{"id": "DTWEXBGS", "value": 120.0, "direction": "down"}], None) is None

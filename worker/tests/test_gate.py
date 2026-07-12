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


# =====================================================================
# Discipline guards (opt-in; the base tests above prove they stay silent
# when their inputs are not supplied).
# =====================================================================
def test_stop_missing_blocks():
    res = evaluate_gate(**{**BASE, "stop": None})
    codes = {(w["code"], w["severity"]) for w in res["warnings"]}
    assert ("stop_missing", "block") in codes
    assert res["has_blocking_warnings"] is True


def test_stop_too_tight_vs_atr_warns():
    # stop distance = 10; ATR=8, k=1.5 -> floor 12 -> 10 < 12 -> warn.
    res = evaluate_gate(**{**BASE, "atr": 8.0, "stop_atr_min_multiple": 1.5})
    assert "stop_too_tight" in _codes(res)
    # wider stop clears the floor -> no warning.
    ok = evaluate_gate(**{**BASE, "stop": 1980.0, "atr": 8.0, "stop_atr_min_multiple": 1.5})
    assert "stop_too_tight" not in _codes(ok)


def test_countertrend_short_in_uptrend_warns_and_cites_rule():
    tech = {"ma": [{"period": 200, "above": True}, {"period": 50, "above": True}]}
    res = evaluate_gate(**{**BASE, "side": "short", "technicals": tech})
    assert "countertrend" in _codes(res)
    msg = next(w["message"] for w in res["warnings"] if w["code"] == "countertrend")
    assert "2500" in msg and "ribasso" in msg.lower()
    # long in the SAME uptrend -> no countertrend warning.
    ok = evaluate_gate(**{**BASE, "side": "long", "technicals": tech})
    assert "countertrend" not in _codes(ok)


def test_countertrend_long_in_downtrend_warns():
    tech = {"ma": [{"period": 200, "above": False}, {"period": 50, "above": False}]}
    assert "countertrend" in _codes(evaluate_gate(**{**BASE, "side": "long", "technicals": tech}))
    assert "countertrend" not in _codes(evaluate_gate(**{**BASE, "side": "short", "technicals": tech}))


def test_reentry_same_losing_direction_warns():
    closed = [{"side": "long", "pnl": -500.0}, {"side": "short", "pnl": -800.0}]
    res = evaluate_gate(**{**BASE, "side": "long", "recent_closed_same_symbol": closed})
    assert "reentry_losing" in _codes(res)
    # opposite side of the loss -> no warning (the short loss doesn't trigger a long).
    ok = evaluate_gate(**{**BASE, "side": "long", "recent_closed_same_symbol": [{"side": "short", "pnl": -800.0}]})
    assert "reentry_losing" not in _codes(ok)


def test_adding_to_open_loser_warns():
    opens = [{"side": "long", "pnl": -300.0}]
    assert "adding_to_loser" in _codes(evaluate_gate(**{**BASE, "side": "long", "open_same_symbol": opens}))
    # a winning open position in the same dir does not trigger it.
    assert "adding_to_loser" not in _codes(evaluate_gate(**{**BASE, "side": "long", "open_same_symbol": [{"side": "long", "pnl": 200.0}]}))


def test_thesis_required_only_when_requested():
    assert "thesis_missing" not in _codes(evaluate_gate(**BASE))                    # opt-in off
    assert "thesis_missing" in _codes(evaluate_gate(**{**BASE, "require_thesis": True}))
    assert "thesis_missing" not in _codes(evaluate_gate(**{**BASE, "require_thesis": True, "thesis": "rates rolling over"}))


def test_budget_cap_warns_and_blocks():
    caps = {"day": {"max": 1500, "mode": "warn"}}
    used = {"day": 800.0}   # +1000 new = 1800 > 1500 -> warn
    res = evaluate_gate(**{**BASE, "budget_caps": caps, "budget_used": used})
    assert "budget_day" in _codes(res) and res["has_blocking_warnings"] is False
    # block mode -> blocking
    blocked = evaluate_gate(**{**BASE, "budget_caps": {"day": {"max": 1500, "mode": "block"}}, "budget_used": used})
    assert blocked["has_blocking_warnings"] is True
    # under the cap -> silent
    ok = evaluate_gate(**{**BASE, "budget_caps": caps, "budget_used": {"day": 100.0}})
    assert "budget_day" not in _codes(ok)


def test_journal_draft_records_ignored_warnings():
    tech = {"ma": [{"period": 200, "above": True}, {"period": 50, "above": True}]}
    res = evaluate_gate(**{**BASE, "side": "short", "technicals": tech, "thesis": "x"})
    assert "countertrend" in res["journal_draft"]["notes"]


# =====================================================================
# Kill-switch (Part C) — pre-mortem rules the user set when lucid.
# =====================================================================
from datetime import datetime as _dt, timezone as _tz, timedelta as _td
from app.gate import consecutive_losses, cooldown_hit


def test_consecutive_losses_counts_trailing_run():
    trades = [{"pnl": -1}, {"pnl": -1}, {"pnl": -1}, {"pnl": 2}, {"pnl": -1}]  # newest first
    assert consecutive_losses(trades) == 3
    assert consecutive_losses([{"pnl": 5}, {"pnl": -1}]) == 0     # last trade was a win
    assert consecutive_losses([]) == 0


def test_cooldown_hit_same_symbol_direction_window():
    now = _dt(2026, 7, 12, 12, 0, tzinfo=_tz.utc)
    stops = [{"symbol": "GC=F", "side": "long", "closed_at": (now - _td(hours=3)).isoformat()}]
    assert cooldown_hit(stops, "GC=F", "long", now, 24) is not None
    assert cooldown_hit(stops, "GC=F", "short", now, 24) is None     # other direction
    assert cooldown_hit(stops, "GC=F", "long", now, 2) is None       # outside 2h window


KS = {"enabled": True, "max_consecutive_losses": 3}


def test_kill_switch_blocks_after_n_losses():
    res = evaluate_gate(**{**BASE, "killswitch": KS, "consecutive_loss_count": 3})
    codes = {(w["code"], w["severity"]) for w in res["warnings"]}
    assert ("kill_switch_losses", "block") in codes and res["has_blocking_warnings"] is True
    # under the limit -> no block
    assert "kill_switch_losses" not in _codes(evaluate_gate(**{**BASE, "killswitch": KS, "consecutive_loss_count": 2}))
    # disabled -> never blocks
    assert "kill_switch_losses" not in _codes(evaluate_gate(**{**BASE, "killswitch": {"enabled": False}, "consecutive_loss_count": 9}))


def test_cooldown_blocks_revenge_entry():
    res = evaluate_gate(**{**BASE, "killswitch": KS, "cooldown": {"hours_ago": 3.0, "cooldown_hours": 24}})
    assert ("cooldown", "block") in {(w["code"], w["severity"]) for w in res["warnings"]}
    assert res["metrics"]["consecutive_losses"] == 0

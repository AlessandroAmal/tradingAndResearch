"""Tests for journal aggregation (exact stats) and the AI review (mocked).

Known-value checks for win rate, R-multiple stats, thesis-played-out rate,
and total P&L; the AI call is mocked (no network).
"""
import math

from app.ai.journal import aggregate_journal, generate_journal_review, realized_r

MULT = {"NVDA": 1.0, "GC=F": 10.0}


def _e(**kw):
    base = dict(symbol="NVDA", outcome=None, pnl=None, entry_price=None,
               stop=None, size=None, thesis_played_out=None)
    base.update(kw)
    return base


# --- realized R -------------------------------------------------------
def test_realized_r_win_and_loss():
    # entry 100, stop 95, size 200 -> risk 1000; pnl 2000 -> +2R
    assert realized_r(_e(entry_price=100, stop=95, size=200, pnl=2000), 1.0) == 2.0
    # pnl -1000 -> -1R
    assert realized_r(_e(entry_price=100, stop=95, size=200, pnl=-1000), 1.0) == -1.0


def test_realized_r_with_multiplier():
    # mult 10 -> risk |100-95|*20*10 = 1000; pnl 1000 -> +1R
    assert realized_r(_e(symbol="GC=F", entry_price=100, stop=95, size=20, pnl=1000), 10.0) == 1.0


def test_realized_r_none_when_incomplete():
    assert realized_r(_e(entry_price=100, size=200, pnl=500), 1.0) is None  # no stop
    assert realized_r(_e(entry_price=100, stop=100, size=200, pnl=0), 1.0) is None  # zero risk


# --- aggregation ------------------------------------------------------
def test_aggregate_empty():
    s = aggregate_journal([], MULT)
    assert s["total"] == 0 and s["closed"] == 0
    assert s["win_rate_pct"] is None and s["avg_r"] is None and s["total_pnl"] is None


def test_aggregate_known_values():
    entries = [
        _e(outcome="win", entry_price=100, stop=95, size=200, pnl=2000, thesis_played_out=True),
        _e(outcome="loss", entry_price=100, stop=95, size=200, pnl=-1000, thesis_played_out=False),
        _e(outcome="win", entry_price=100, stop=90, size=100, pnl=1000, thesis_played_out=True),
        _e(outcome="breakeven", entry_price=50, stop=49, size=100, pnl=0),
        _e(outcome=None),  # open, no data
    ]
    s = aggregate_journal(entries, MULT)
    assert s["total"] == 5
    assert s["open"] == 1
    assert s["closed"] == 4
    assert (s["wins"], s["losses"], s["breakevens"]) == (2, 1, 1)
    assert math.isclose(s["win_rate_pct"], 50.0)             # 2 / 4
    assert s["thesis_tracked"] == 3
    assert s["thesis_played_out"] == 2
    assert math.isclose(s["thesis_played_out_rate_pct"], 2 / 3 * 100)
    # R values: +2, -1, +1 (NVDA), and breakeven 0/risk = 0 -> 4 values
    # risks: 1000, 1000, 1000, 100 -> R = 2, -1, 1, 0
    assert s["r_count"] == 4
    assert math.isclose(s["avg_r"], (2 - 1 + 1 + 0) / 4)
    assert math.isclose(s["total_pnl"], 2000)


# --- AI review (mocked) ----------------------------------------------
class FakeAI:
    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    def json_call(self, *, model, system, user, schema, max_tokens):
        self.calls.append({"model": model, "user": user})
        return self._payload


def test_generate_review_parses_and_keeps_stats_in_prompt():
    stats = aggregate_journal(
        [_e(outcome="win", entry_price=100, stop=95, size=200, pnl=2000)], MULT
    )
    ai = FakeAI({
        "content": "- Tech longs working.",
        "sample_size_note": "Only 1 trade — not significant.",
        "uncertainty_note": "Tentative.",
    })
    out = generate_journal_review(ai, model="claude-sonnet-4-6", stats=stats, entries=[])
    assert out["content"].startswith("- Tech longs")
    assert out["sample_size_note"]
    assert ai.calls[0]["model"] == "claude-sonnet-4-6"
    # exact stats are embedded in the prompt (win rate 100%)
    assert "Win rate:" in ai.calls[0]["user"]


def test_generate_review_none_on_failure():
    stats = aggregate_journal([], MULT)  # complete stats dict (contract)
    out = generate_journal_review(FakeAI(None), model="m", stats=stats, entries=[])
    assert out is None


def test_generate_review_fills_default_uncertainty():
    stats = aggregate_journal([], MULT)
    out = generate_journal_review(
        FakeAI({"content": "x", "sample_size_note": "s"}),  # no uncertainty_note
        model="m", stats=stats, entries=[],
    )
    assert out["uncertainty_note"]  # defaulted, never empty

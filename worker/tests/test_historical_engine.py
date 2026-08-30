"""Unified historical engine (AUDIT2 §6.A #4): forward returns, effective n, and
the STREAK as a regime. The base rate + conditional distributions are rebuilt on
this core; their own suites (test_base_rates, test_prospects_conditional) guard
that outputs are unchanged."""
from pytest import approx

from app.historical_engine import (
    effective_n, forward_returns, forward_stats, matched_forward_returns,
    run_lengths, streak_occurrence_indices, streak_regime,
)


def test_forward_returns_no_lookahead():
    closes = [100, 110, 121, 133.1]         # +10% each step
    fwd = forward_returns(closes, 1)
    assert fwd[0] == approx(0.1) and fwd[2] == approx(0.1)
    assert fwd[-1] is None                  # last t+1 out of range


def test_effective_n_discounts_overlap():
    assert effective_n(2380, 21) == 113
    assert effective_n(200, 1) == 200
    assert effective_n(5, 21) == 0


def test_run_lengths_and_streak_regime():
    closes = [100, 101, 102, 103, 102, 101]   # up,up,up, down,down
    lengths, dirs = run_lengths(closes)
    assert lengths == [0, 1, 2, 3, 1, 2]
    assert dirs == ['flat', 'up', 'up', 'up', 'down', 'down']
    reg = streak_regime(closes)
    assert reg == [None, 'up:1', 'up:2', 'up:3', 'down:1', 'down:2']


def test_streak_occurrence_indices_matches_regime():
    closes = [100, 101, 102, 100, 101, 102]   # up:1,up:2 then down:1(idx3) up:1,up:2
    # up-run reaching exactly length 2 happens at idx 2 and idx 5
    assert streak_occurrence_indices(closes, 2, 'up') == [2, 5]
    assert streak_occurrence_indices(closes, 1, 'down') == [3]


def test_matched_forward_returns_and_stats():
    closes = [100, 110, 121, 100, 110, 121]
    idx = streak_occurrence_indices(closes, 1, 'up')   # idx 1 (up:1) and idx 4 (up:1)
    rets = matched_forward_returns(closes, idx, 1)      # 121/110-1, (none for idx4: 121 is last? idx4+1=5 ok)
    assert len(rets) == 2 and rets[0] == approx(0.1)
    s = forward_stats(rets, 1)
    assert s['n'] == 2 and s['pct_up'] == 1.0 and s['median'] == approx(0.1)
    assert forward_stats([], 5)['n'] == 0

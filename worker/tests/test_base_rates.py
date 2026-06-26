"""Tests for the base-rate engine — the delicate, honesty-critical math.

Series are hand-built so the expected occurrence count `n` and the forward
outcome distribution can be verified by hand (see comments).
"""
import math

from app.base_rates import streak_base_rate


def test_no_streak_when_flat():
    res = streak_base_rate([100, 100, 100], min_sample=5)
    assert res.status == "no_streak"
    assert res.length == 0 and res.sample_size == 0
    assert res.horizons == []


def test_never_happened_returns_no_distribution():
    # Strictly falling -> current down-streak length 5, only ever reached at the
    # final (current) bar, which has no forward data: n == 0 -> 'never'.
    closes = [10, 9, 8, 7, 6, 5]
    res = streak_base_rate(closes, min_sample=20)
    assert res.direction == "down" and res.length == 5
    assert res.status == "never"
    assert res.sample_size == 0
    assert res.in_progress is True
    assert res.horizons == []          # NO probability for an unseen streak
    assert "mai" in res.message.lower()


def test_insufficient_sample_is_flagged_but_counts_n():
    # Alternating 100/99: current down-streak length 1; run==1-down occurs at
    # every down day. closes has 6 down days; the last is the current bar (no
    # forward), so n = 5 past occurrences. Each is followed by an up day.
    closes = [100, 99, 100, 99, 100, 99, 100, 99, 100, 99, 100, 99]
    res = streak_base_rate(closes, horizons=(1,), min_sample=20)
    assert res.length == 1 and res.direction == "down"
    assert res.sample_size == 5
    assert res.status == "insufficient"          # 5 < 20 -> no conclusion
    h1 = res.horizons[0]
    assert h1.horizon == 1 and h1.n == 5
    assert h1.pct_up == 1.0                       # every time, next day was up
    assert h1.mean_return is not None and h1.mean_return > 0


def test_ok_status_and_forward_distribution():
    # Hand-built moves (±2): four run==2-down episodes; the last is the current
    # bar (no forward) -> n = 3 past occurrences.
    # Next-day outcomes after the 3 past episodes: up, down, up -> pct_up = 2/3.
    closes = [100, 102, 100, 98, 100, 98, 96, 94, 96, 94, 92, 94, 92, 90]
    res = streak_base_rate(closes, horizons=(1, 3), min_sample=3)
    assert res.direction == "down" and res.length == 2
    assert res.sample_size == 3
    assert res.status == "ok"                     # 3 >= min_sample(3)
    h1 = next(h for h in res.horizons if h.horizon == 1)
    assert h1.n == 3
    assert math.isclose(h1.pct_up, 2 / 3, abs_tol=1e-9)
    # 3 days out all three episodes were lower -> pct_up == 0.
    h3 = next(h for h in res.horizons if h.horizon == 3)
    assert h3.n == 3 and h3.pct_up == 0.0


def test_caveat_always_present():
    res = streak_base_rate([100, 99, 98], min_sample=20)
    assert "rimbalzo" in res.caveat.lower()       # the fixed honesty note
    # And the result serialises cleanly for storage.
    d = res.to_dict()
    assert "sample_size" in d and "caveat" in d and "horizons" in d

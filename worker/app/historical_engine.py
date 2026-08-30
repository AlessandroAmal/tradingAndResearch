"""Unified historical engine — ONE core for "what happened historically, with n".

Both the streak base rate (decision board) and the driver-regime conditional
distributions (prospects) are the SAME question — the forward-return frequency
over the past days that matched a CONDITION — and were two implementations
(AUDIT/AUDIT2 duplication b). This module is the single engine:

  * `forward_returns(closes, h)` — r_{t→t+h}, no look-ahead;
  * `effective_n(n, h)`         — independent-window count (≈ n/h) for overlaps;
  * regimes as per-index labels the caller conditions on — including the STREAK
    as just one regime (`streak_regime`), so a run of N up/down days is selectable
    exactly like a tercile or a rising/falling driver;
  * `matched_forward_returns` + `forward_stats` — select the matching days and
    summarise them (n, effective n, % up, mean, median).

PURE & honest: n is always present; nothing here is a forecast or a probability
of reversal (rarity ≠ reversal — gambler's fallacy). Consumed by `base_rates.py`
and `prospects/conditional.py`; tested in `test_historical_engine.py` plus the
existing base-rate/conditional suites (outputs unchanged).
"""
from __future__ import annotations

from collections.abc import Sequence


def forward_returns(closes: Sequence[float], h: int) -> list[float | None]:
    """r_{t→t+h} aligned to t (None where t+h is out of range or price ≤ 0)."""
    n = len(closes)
    out: list[float | None] = []
    for t in range(n):
        if t + h < n and closes[t] > 0:
            out.append(closes[t + h] / closes[t] - 1.0)
        else:
            out.append(None)
    return out


def effective_n(n: int, h: int) -> int:
    """Independent-window count for overlapping h-day returns (≈ n/h, ≥ 0)."""
    return max(0, n // max(h, 1))


def run_lengths(closes: Sequence[float]) -> tuple[list[int], list[str]]:
    """Trailing run length + direction at each index (index 0 = no prior run)."""
    n = len(closes)
    lengths = [0] * n
    dirs = ["flat"] * n
    for i in range(1, n):
        diff = closes[i] - closes[i - 1]
        if diff == 0:
            lengths[i], dirs[i] = 0, "flat"
        else:
            d = "up" if diff > 0 else "down"
            if d == dirs[i - 1] and lengths[i - 1] > 0:
                lengths[i] = lengths[i - 1] + 1
            else:
                lengths[i] = 1
            dirs[i] = d
    return lengths, dirs


def streak_regime(closes: Sequence[float]) -> list[str | None]:
    """The STREAK as a per-index regime label ('up:5', 'down:3', 'flat', None) — so
    a run of N days in a direction is a selectable regime like any driver's."""
    lengths, dirs = run_lengths(closes)
    out: list[str | None] = []
    for i in range(len(closes)):
        if i == 0:
            out.append(None)
        elif dirs[i] == "flat" or lengths[i] == 0:
            out.append("flat")
        else:
            out.append(f"{dirs[i]}:{lengths[i]}")
    return out


def streak_occurrence_indices(closes: Sequence[float], length: int, direction: str) -> list[int]:
    """Indices where the trailing run reached EXACTLY `length` in `direction` — the
    base-rate 'occurrence' definition, expressed via the streak regime."""
    label = f"{direction}:{length}"
    return [i for i, lab in enumerate(streak_regime(closes)) if lab == label]


def matched_forward_returns(closes: Sequence[float], indices: Sequence[int], h: int) -> list[float]:
    """Forward-h returns for the given matched indices (skip where t+h out of range)."""
    n = len(closes)
    return [closes[i + h] / closes[i] - 1.0
            for i in indices if i + h < n and closes[i] != 0]


def forward_stats(rets: Sequence[float], h: int) -> dict:
    """Common summary of a set of matched forward returns: n, effective n, % up,
    mean, median. (The prospects layer adds p16/p84 + block bootstrap on top.)"""
    xs = list(rets)
    n = len(xs)
    if n == 0:
        return {"n": 0, "n_effective": 0, "pct_up": None, "mean": None, "median": None}
    ups = sum(1 for r in xs if r > 0)
    return {"n": n, "n_effective": effective_n(n, h), "pct_up": ups / n,
            "mean": sum(xs) / n, "median": _median(xs)}


def _median(xs: Sequence[float]) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2.0

"""Conditional historical distributions — forward returns given a driver regime.

For horizon h, the distribution of h-day forward returns CONDITIONED on the state
of one driver (A) or two drivers together (B). Everything is a historical
FREQUENCY WITH its sample size — never a forecast (CLAUDE.md).

Two honesty guards that matter:
  * EFFECTIVE n — overlapping h-day windows are NOT independent. 5000 daily obs of
    a 252-day return are ~20 independent draws, not 5000. We report n_effective
    (≈ n/h) alongside raw n, and gate on the effective one.
  * BLOCK BOOTSTRAP — intervals are resampled in blocks (length ≈ h) so the
    autocorrelation of overlapping windows is preserved, not washed out.

Regimes are deliberately simple and documented: a driver is in the 'low'/'mid'/
'high' TERCILE of its own history, or (for change-based drivers) 'falling'/'rising'.
Pure; tested in test_prospects_conditional.py.
"""
from __future__ import annotations

import random
import statistics
from collections.abc import Mapping, Sequence

# Shared historical engine (AUDIT2 §6.A #4): one core for forward returns +
# effective n, and the STREAK as a selectable regime alongside terciles/direction.
from ..historical_engine import effective_n, forward_returns, streak_regime  # noqa: F401


def tercile_regime(values: Sequence[float | None]) -> list[str | None]:
    """Label each point low/mid/high by its value's tercile over the WHOLE series.
    (For a calibration study this is acceptable; the runner uses causal values.)"""
    clean = sorted(v for v in values if v is not None)
    if len(clean) < 3:
        return [None] * len(values)
    lo = clean[len(clean) // 3]
    hi = clean[2 * len(clean) // 3]
    out: list[str | None] = []
    for v in values:
        if v is None:
            out.append(None)
        elif v <= lo:
            out.append("low")
        elif v >= hi:
            out.append("high")
        else:
            out.append("mid")
    return out


def direction_regime(values: Sequence[float | None], window: int = 20) -> list[str | None]:
    """'rising'/'falling'/'flat' by the sign of the change over `window` (causal)."""
    out: list[str | None] = []
    for t in range(len(values)):
        v, v0 = values[t], (values[t - window] if t >= window else None)
        if v is None or v0 is None:
            out.append(None)
        elif v > v0:
            out.append("rising")
        elif v < v0:
            out.append("falling")
        else:
            out.append("flat")
    return out


def _block_bootstrap_ci(rets: Sequence[float], h: int, *, n_boot: int = 800,
                        seed: int = 4242) -> dict:
    """Median + 68/95 intervals via block bootstrap (block length ≈ h) so the
    autocorrelation of overlapping windows is preserved."""
    vals = list(rets)
    n = len(vals)
    block = max(1, min(h, n))
    rng = random.Random(seed)
    meds: list[float] = []
    for _ in range(n_boot):
        sample: list[float] = []
        while len(sample) < n:
            start = rng.randrange(n)
            sample.extend(vals[start:start + block])
        meds.append(statistics.median(sample[:n]))
    meds.sort()

    def q(p: float) -> float:
        return meds[min(len(meds) - 1, int(p * len(meds)))]

    return {"median": statistics.median(vals),
            "median_ci68": (q(0.16), q(0.84)), "median_ci95": (q(0.025), q(0.975))}


def _distribution(rets: Sequence[float], h: int, level_ret: float | None) -> dict:
    """Empirical distribution stats for a set of forward returns."""
    vals = sorted(rets)
    n = len(vals)

    def pctl(p: float) -> float:
        return vals[min(n - 1, int(p * n))]

    out = {
        "n": n, "n_effective": effective_n(n, h),
        "median": statistics.median(vals),
        "p16": pctl(0.16), "p84": pctl(0.84),
        "p2_5": pctl(0.025), "p97_5": pctl(0.975),
        "mean": sum(vals) / n,
    }
    out.update(_block_bootstrap_ci(vals, h))
    if level_ret is not None:
        out["prob_above"] = sum(1 for v in vals if v >= level_ret) / n
        out["prob_below"] = sum(1 for v in vals if v < level_ret) / n
        out["level_ret"] = level_ret
    return out


def conditional_distribution(
    closes: Sequence[float], h: int, regimes: Mapping[str, Sequence[str | None]],
    conditions: Mapping[str, str], *, min_effective: int = 5, level_ret: float | None = None,
) -> dict:
    """Forward-h return distribution where EVERY (driver→state) in `conditions`
    holds at t. `regimes` maps driver -> per-t regime labels. Returns the stats +
    n/n_effective + a `sufficient` flag (on EFFECTIVE n) + the conditions used."""
    fwd = forward_returns(closes, h)
    rets: list[float] = []
    for t in range(len(closes)):
        if fwd[t] is None:
            continue
        if all(regimes.get(drv, [None] * len(closes))[t] == state
               for drv, state in conditions.items()):
            rets.append(fwd[t])
    if len(rets) < 2:
        return {"conditions": dict(conditions), "n": len(rets), "n_effective": 0,
                "min_effective": min_effective, "sufficient": False,
                "note": "campione insufficiente, non mostrato come probabilità"}
    dist = _distribution(rets, h, level_ret)
    dist["conditions"] = dict(conditions)
    dist["min_effective"] = min_effective
    dist["sufficient"] = dist["n_effective"] >= min_effective
    if not dist["sufficient"]:
        dist["note"] = (f"n effettivo {dist['n_effective']} < {min_effective}: "
                        "campione insufficiente (finestre sovrapposte), non una probabilità")
    return dist

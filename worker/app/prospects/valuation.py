"""Valuation → long-horizon return (indices & stocks only).

The one horizon where fundamentals matter: starting valuation vs the return over
the NEXT 3-5 years. Measured on whatever history is available, conditioned on the
CURRENT valuation bucket. The honesty here is brutal by necessity: 3-5y windows
over ~10-20y of data give a HANDFUL of independent observations (effective n often
2-4). We report it and caveat hard — "indicativo", never a forecast.

Not applicable to FX/commodity (no earnings-based valuation). Pure; tested in
test_prospects_valuation.py.
"""
from __future__ import annotations

import statistics
from collections.abc import Sequence

from .conditional import effective_n

TRADING_YEAR = 252


def forward_return(closes: Sequence[float], t: int, years: int) -> float | None:
    h = years * TRADING_YEAR
    if t + h < len(closes) and closes[t] > 0:
        return closes[t + h] / closes[t] - 1.0
    return None


def _bucket(v: float, lo: float, hi: float) -> str:
    return "cheap" if v <= lo else "expensive" if v >= hi else "fair"


def valuation_return_distribution(
    closes: Sequence[float], valuations: Sequence[float | None], years: int,
    current_valuation: float | None, *, min_effective: int = 2,
) -> dict:
    """Distribution of `years`-ahead returns for points whose valuation is in the
    SAME bucket (cheap/fair/expensive terciles) as `current_valuation`.

    Returns median + 68/95 range + n + effective n + a strong caveat."""
    clean = sorted(v for v in valuations if v is not None)
    if len(clean) < 3 or current_valuation is None:
        return {"available": False, "years": years,
                "note": "valutazione storica insufficiente o valutazione corrente assente"}
    lo, hi = clean[len(clean) // 3], clean[2 * len(clean) // 3]
    target = _bucket(current_valuation, lo, hi)

    rets: list[float] = []
    for t in range(len(closes)):
        v = valuations[t] if t < len(valuations) else None
        if v is None:
            continue
        if _bucket(v, lo, hi) != target:
            continue
        fr = forward_return(closes, t, years)
        if fr is not None:
            rets.append(fr)
    n = len(rets)
    if n < 2:
        return {"available": False, "years": years, "bucket": target, "n": n,
                "note": "campione insufficiente per questa fascia di valutazione"}
    vals = sorted(rets)

    def pctl(p: float) -> float:
        return vals[min(n - 1, int(p * n))]

    n_eff = effective_n(n, years * TRADING_YEAR)
    return {
        "available": True, "years": years, "bucket": target,
        "current_valuation": current_valuation, "cheap_below": lo, "expensive_above": hi,
        "n": n, "n_effective": n_eff, "sufficient": n_eff >= min_effective,
        "median": statistics.median(vals), "p16": pctl(0.16), "p84": pctl(0.84),
        "p2_5": pctl(0.025), "p97_5": pctl(0.975),
        "note": ("ATTENZIONE: osservazioni indipendenti pochissime "
                 f"(n effettivo ≈ {n_eff}); relazione valutazione→rendimento indicativa, "
                 "non una previsione. Storico condizionato, non garanzia."),
    }

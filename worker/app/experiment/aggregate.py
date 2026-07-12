"""Aggregate CLOSED experiment positions into evidence. PURE & TESTED.

Groups the paper outcomes by whatever dimensions the view asks for (event ×
instrument × delay × horizon × direction × surprise) and reports n, % positive,
mean/median return and dispersion. `n` is always present; below `min_sample` the
cell is `sufficient=False` — a small sample is NOT a probability, and none of
this is a signal. Mirrored client-side in `lib/experiment.js`.
"""
from __future__ import annotations

import statistics
from collections.abc import Mapping, Sequence


def flatten(p: Mapping) -> dict:
    """One closed experiment position → its measurable fields."""
    c = p.get("entry_conditions") or {}
    sur = c.get("surprise") or {}
    ret = c.get("return_pct")
    if ret is None and p.get("realized_pnl") is not None and p.get("entry"):
        try:
            ret = float(p["realized_pnl"]) / float(p["entry"])   # size=1 by construction
        except (TypeError, ValueError, ZeroDivisionError):
            ret = None
    return {
        "event": c.get("event"),
        "symbol": p.get("symbol"),
        "delay_min": c.get("delay_min"),
        "horizon": c.get("horizon"),
        "direction": c.get("direction"),
        "surprise_dir": sur.get("direction"),
        "return_pct": ret,
    }


def aggregate_experiments(positions: Sequence[Mapping], group_keys: Sequence[str],
                          *, min_sample: int = 20) -> list[dict]:
    """Group closed experiments by `group_keys`, with honest per-cell stats."""
    rows = [flatten(p) for p in positions if p.get("status") == "closed"]
    rows = [r for r in rows if r["return_pct"] is not None]

    groups: dict[tuple, list[float]] = {}
    for r in rows:
        gk = tuple(r.get(k) for k in group_keys)
        groups.setdefault(gk, []).append(float(r["return_pct"]))

    out: list[dict] = []
    for gk, rets in groups.items():
        n = len(rets)
        out.append({
            "group": dict(zip(group_keys, gk)),
            "n": n,
            "pct_positive": sum(1 for x in rets if x > 0) / n,
            "mean_return": sum(rets) / n,
            "median_return": statistics.median(rets),
            "stdev": statistics.pstdev(rets) if n > 1 else None,
            "sufficient": n >= min_sample,
        })
    out.sort(key=lambda c: c["n"], reverse=True)
    return out

"""Thematic concentration — a REAL risk the book can hide. PURE & TESTED.

Positions on different tickers can still be the SAME bet: MSFT + AVGO + VRT +
NVDA + GOOGL are largely one wager on AI / data-center capex. In a de-rating of
that thesis they fall together, so the apparent diversification is not real.

`theme_concentration` groups open positions by their instrument's thematic tags
and returns each theme's weight of the book (by notional), flagging themes shared
by >= `warn_min_positions` distinct names. READ-ONLY: it warns, it never trades,
and it makes NO directional call. Mirrored client-side in `lib/concentration.js`.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

# Human labels for the thematic tags used in config (universe[].themes).
THEME_LABELS = {
    "ai_datacenter": "AI / data-center capex",
    "semis": "Semiconduttori",
    "ev": "Veicoli elettrici",
    "pharma": "Farmaceutico",
    "financials": "Finanziari",
}


def theme_concentration(
    positions: Sequence[Mapping],
    themes_by_symbol: Mapping[str, Sequence[str]],
    *,
    warn_min_positions: int = 2,
    theme_labels: Mapping[str, str] | None = None,
) -> list[dict]:
    """Per-theme exposure of the book.

    `positions` items need `symbol` and `notional` (currency exposure; the caller
    computes size*price*point_value). Returns a list sorted with the flagged,
    heaviest themes first. A theme is `concentrated` when >= `warn_min_positions`
    DISTINCT names share it. Weight is the theme's share of total book notional.
    """
    labels = {**THEME_LABELS, **dict(theme_labels or {})}
    total = sum(abs(float(p.get("notional") or 0.0)) for p in positions) or 0.0

    by_theme: dict[str, dict] = {}
    for p in positions:
        sym = p.get("symbol")
        notl = abs(float(p.get("notional") or 0.0))
        for th in themes_by_symbol.get(sym, []) or []:
            e = by_theme.setdefault(th, {"symbols": set(), "notional": 0.0})
            e["symbols"].add(sym)
            e["notional"] += notl

    out: list[dict] = []
    for th, e in by_theme.items():
        n = len(e["symbols"])
        out.append({
            "theme": th,
            "label": labels.get(th, th),
            "symbols": sorted(e["symbols"]),
            "positions": n,
            "notional": e["notional"],
            "weight": (e["notional"] / total) if total > 0 else None,
            "concentrated": n >= warn_min_positions,
        })
    # Flagged first, then by notional (heaviest exposure on top).
    out.sort(key=lambda x: (x["concentrated"], x["notional"]), reverse=True)
    return out

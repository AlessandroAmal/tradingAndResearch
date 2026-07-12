"""Surprise = released value vs consensus. PURE & TESTED.

Uses the `actual` / `forecast` already stored on calendar events (FMP economic
calendar). Values are free-text ("206K", "3.1%", "-0.2") so we parse leniently.
When the consensus is missing we return None and say so — we NEVER invent an
estimate (CLAUDE.md §5). This is a factual classification of the release, not a
directional prediction of any instrument.
"""
from __future__ import annotations

import re

# How far apart actual and forecast must be (as a fraction of |forecast|, or an
# absolute floor) before we call it a surprise rather than "in line".
_REL_TOL = 0.001


def parse_number(s) -> float | None:
    """Parse a released/consensus figure like '206K', '3.1%', '-0.2', '1.2M'."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    txt = str(s).strip().replace(",", "")
    if not txt or txt.lower() in ("n/a", "na", "-", "--"):
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", txt)
    if not m:
        return None
    val = float(m.group())
    tail = txt[m.end():].lstrip()
    mult = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}.get(tail[:1].lower()) if tail else None
    if mult:
        val *= mult
    return val


def surprise_direction(actual, forecast, *, rel_tol: float = _REL_TOL) -> dict:
    """Classify the release vs consensus.

    Returns {available, direction, actual, forecast, delta, note}. `direction` ∈
    {positive, negative, inline}; None + available=False when consensus is absent.
    NOTE: 'positive' means the DATA came in above consensus — it is NOT a call on
    any instrument's direction (a hot CPI is 'positive surprise' yet bearish for
    bonds/gold; the experiment measures that, it doesn't assume it).
    """
    a = parse_number(actual)
    f = parse_number(forecast)
    if a is None or f is None:
        return {"available": False, "direction": None, "actual": a, "forecast": f,
                "delta": None,
                "note": "Consenso non disponibile da fonte gratuita: sorpresa non calcolata (nessuna stima inventata)."}
    delta = a - f
    tol = max(abs(f) * rel_tol, 1e-9)
    if delta > tol:
        direction = "positive"
    elif delta < -tol:
        direction = "negative"
    else:
        direction = "inline"
    return {"available": True, "direction": direction, "actual": a, "forecast": f,
            "delta": delta,
            "note": "Sorpresa = dato USCITO vs consenso; è un fatto sul dato, non una direzione sullo strumento."}

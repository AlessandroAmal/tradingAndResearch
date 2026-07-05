"""Full-picture panel — ALL factor states SIDE BY SIDE, never fused (M9).

For a single stock the honest "everything together" lives in exactly two places:
  * the AI synthesis (qualitative integration, in prose), and
  * the option-IMPLIED probability (the market has already weighed everything).

This module builds the AT-A-GLANCE board: each factor shown with its own value
and a one-word STATE (colour = state only). It deliberately produces NO composite
score and NO directional probability — there is no aggregate field anywhere. The
implied odds are passed through and merely FLAGGED as the integrated number.

HARD RULES (CLAUDE.md §1, §5): no fabricated directional number; no score fusing
fundamentals + macro + technical; every factor carries its own honest label.

Pure (no I/O); unit-tested in `worker/tests/test_full_picture.py`.
"""
from __future__ import annotations

from collections.abc import Mapping

FIXED_LABEL = (
    "Ogni fattore col suo stato — NON sono sommati in un punteggio. "
    "L'integrazione è l'analisi AI (qualitativa); gli odds di tutto-insieme sono "
    "la probabilità implicita (il mercato ha già pesato tutto)."
)

# Directional words reused for macro/technical/skew LEANS (each is a lean of its
# OWN category only — never a cross-category fusion).
_LEAN_WORD = {"bullish": "rialzista", "bearish": "ribassista", "neutral": "neutro"}
_LEAN_TONE = {"bullish": "good", "bearish": "bad", "neutral": "neutral"}


def _factor(key, label, value, state, tone) -> dict:
    """tone ∈ {good, bad, neutral, watch, none}; drives COLOUR (state) only."""
    return {"key": key, "label": label, "value": value, "state": state, "tone": tone}


def _pct(v) -> str | None:
    return None if v is None else f"{v * 100:.0f}%"


def _big(v) -> str:
    if v is None:
        return "n/d"
    a = abs(v)
    if a >= 1e12:
        return f"{v / 1e12:.2f}T"
    if a >= 1e9:
        return f"{v / 1e9:.1f}B"
    if a >= 1e6:
        return f"{v / 1e6:.1f}M"
    return f"{v:.0f}"


# --- fundamentals factors (descriptive states, not directional) -------
def _valuation(val: Mapping) -> dict:
    ctx = val.get("context") or {}
    pe = ctx.get("pe") if ctx.get("pe") is not None else (
        val.get("pe_forward") if val.get("pe_forward") is not None else val.get("pe_trailing"))
    if pe is None:
        return _factor("valuation", "Valutazione", "n/d", "n/d", "none")
    band = ctx.get("band") or ("cara" if pe > 30 else "economica" if pe < 12 else "nella media")
    pctl = ctx.get("percentile")
    value = f"P/E {ctx.get('basis', 'forward')} {pe:.0f}" + (
        f" · {pctl * 100:.0f}° pct" if pctl is not None else "")
    return _factor("valuation", "Valutazione", value, band, "none")  # caro/economico ≠ direzione


def _growth(g: Mapping) -> dict:
    rev, ear = g.get("revenue_yoy"), g.get("earnings_yoy")
    if rev is None and ear is None:
        return _factor("growth", "Crescita", "n/d", "n/d", "none")
    parts = []
    if rev is not None:
        parts.append(f"ricavi {_pct(rev)}")
    if ear is not None:
        parts.append(f"utili {_pct(ear)}")
    ref = rev if rev is not None else ear
    state = "in crescita" if ref > 0 else "in calo" if ref < 0 else "piatta"
    tone = "good" if ref > 0 else "bad" if ref < 0 else "neutral"
    return _factor("growth", "Crescita", " · ".join(parts), state, tone)


def _quality(q: Mapping) -> dict:
    nm, roe = q.get("net_margin"), q.get("roe")
    if nm is None and roe is None:
        return _factor("quality", "Qualità", "n/d", "n/d", "none")
    parts = []
    if nm is not None:
        parts.append(f"margine netto {_pct(nm)}")
    if roe is not None:
        parts.append(f"ROE {_pct(roe)}")
    if nm is None:
        state, tone = "n/d", "none"
    elif nm <= 0:
        state, tone = "in perdita", "bad"
    elif nm >= 0.20:
        state, tone = "alta", "good"
    else:
        state, tone = "positiva", "neutral"
    return _factor("quality", "Qualità", " · ".join(parts), state, tone)


def _cash(c: Mapping) -> dict:
    fcf, de = c.get("free_cash_flow"), c.get("debt_to_equity")
    if fcf is None and de is None:
        return _factor("cash", "Cassa / bilancio", "n/d", "n/d", "none")
    value = (f"FCF {_big(fcf)}" if fcf is not None else "FCF n/d") + (
        f" · D/E {de:.0f}" if de is not None else "")
    if fcf is None:
        state, tone = "n/d", "none"
    else:
        state, tone = ("FCF positivo", "good") if fcf > 0 else ("FCF negativo", "bad")
    return _factor("cash", "Cassa / bilancio", value, state, tone)


def _earnings_risk(e: Mapping, days_to_next) -> dict:
    sur = e.get("surprises") or []
    beats = sum(1 for s in sur if s.get("beat"))
    hist = f" · {beats}/{len(sur)} beat" if sur else ""
    if days_to_next is None:
        nd = e.get("next_date")
        value = (nd or "n/d") + hist
        return _factor("earnings_risk", "Rischio utili", value, "n/d" if not nd else "in calendario", "none")
    value = f"tra {days_to_next}g{hist}"
    state, tone = ("imminente", "watch") if days_to_next <= 14 else ("lontano", "neutral")
    return _factor("earnings_risk", "Rischio utili", value, state, tone)


# --- macro / technical / skew leans (each: lean of its OWN category) ---
def _macro(synthesis: Mapping) -> dict:
    facs = [f for f in synthesis.get("factors", [])
            if f.get("included") and f.get("kind") == "directional"
            and str(f.get("key", "")).startswith("macro:")]
    if not facs:
        return _factor("macro", "Contesto macro", "n/d", "n/d", "none")
    net = sum({"bullish": 1, "bearish": -1}.get(f.get("classification"), 0) for f in facs)
    cls = "bullish" if net > 0 else "bearish" if net < 0 else "neutral"
    return _factor("macro", "Contesto macro (sfondo)", f"{len(facs)} driver",
                   _LEAN_WORD[cls], _LEAN_TONE[cls])


def _technical(synthesis: Mapping, technicals: Mapping) -> dict:
    trend = next((f for f in synthesis.get("factors", []) if f.get("key") == "trend_ma"), None)
    cls = trend.get("classification", "neutral") if (trend and trend.get("included")) else "neutral"
    ma200 = next((m for m in technicals.get("ma", []) if m.get("period") == 200), None)
    bits = []
    if ma200 and ma200.get("above") is not None:
        bits.append("sopra MA200" if ma200["above"] else "sotto MA200")
    rsi = technicals.get("rsi", {})
    if rsi.get("value") is not None:
        bits.append(f"RSI {rsi['value']:.0f}")
    sk = technicals.get("streak", {})
    if sk.get("length"):
        bits.append(f"streak {sk['length']}{'↑' if sk.get('direction') == 'up' else '↓'}")
    return _factor("technical", "Contesto tecnico (sfondo)", " · ".join(bits) or "n/d",
                   _LEAN_WORD.get(cls, "neutro"), _LEAN_TONE.get(cls, "neutral"))


def _skew(synthesis: Mapping) -> dict | None:
    sk = next((f for f in synthesis.get("factors", []) if f.get("key") == "skew"), None)
    if not sk:
        return None
    cls = sk.get("classification", "neutral")
    return _factor("skew", "Skew (opzioni)", sk.get("detail", ""), _LEAN_WORD.get(cls, "neutro"),
                   _LEAN_TONE.get(cls, "neutral"))


def build_full_picture(
    fundamentals: Mapping | None,
    synthesis: Mapping | None,
    technicals: Mapping | None,
    implied: Mapping | None,
    *,
    days_to_next_earnings: int | None = None,
) -> dict:
    """All states side by side + the implied odds flagged as the integrated number.

    No aggregate/score field is produced (by design)."""
    f = fundamentals or {}
    s = synthesis or {}
    t = technicals or {}
    factors = [
        _valuation(f.get("valuation") or {}),
        _growth(f.get("growth") or {}),
        _quality(f.get("quality") or {}),
        _cash(f.get("cash") or {}),
        _earnings_risk(f.get("earnings") or {}, days_to_next_earnings),
        _macro(s),
        _technical(s, t),
    ]
    skew = _skew(s)
    if skew:
        factors.append(skew)

    market = s.get("market") or {}
    implied_block = {
        "prob_up": market.get("prob_up"),
        "horizon": market.get("horizon"),
        "highlight": True,
        "label": "Odds impliciti (il numero calibrato — il mercato ha già pesato tutto)",
        "note": market.get("note"),
    }
    return {"factors": factors, "implied": implied_block, "label": FIXED_LABEL}

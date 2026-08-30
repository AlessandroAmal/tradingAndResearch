"""Balance-sheet TRAJECTORY — QoQ/YoY deltas + inflections from stored quarterly
history. PURE & TESTED. Context, already known to the market — never a forecast
and never a directional score.

Given quarterly records (newest first) it produces, per metric: the current value,
the QoQ delta (vs the previous quarter), the YoY delta (vs the same quarter a year
earlier, i.e. 4 quarters back), a sparkline series (oldest→newest), and an
INFLECTION flag when something turns (a margin flips sign, FCF changes sign, debt
accelerates). Percentage-style metrics report absolute point deltas; level metrics
report relative deltas.
"""
from __future__ import annotations

from collections.abc import Sequence

# (key, label, kind) — kind drives how the delta is expressed in the UI.
METRICS: tuple[tuple[str, str, str], ...] = (
    ("revenue", "Ricavi", "level"),
    ("net_income", "Utile netto", "level"),
    ("gross_margin", "Margine lordo", "ratio"),
    ("operating_margin", "Margine operativo", "ratio"),
    ("net_margin", "Margine netto", "ratio"),
    ("fcf", "Free cash flow", "level"),
    ("capex", "Capex", "level"),
    ("cash", "Cassa", "level"),
    ("debt", "Debito", "level"),
    ("eps", "EPS", "level"),
)


def _delta(cur: float | None, prev: float | None, kind: str) -> dict:
    """Absolute delta always; a relative delta for level metrics (None for ratios,
    which are already in points). Returns {abs, rel}."""
    if cur is None or prev is None:
        return {"abs": None, "rel": None}
    ab = cur - prev
    rel = None
    if kind == "level" and prev not in (0, None):
        rel = ab / abs(prev)
    return {"abs": ab, "rel": rel}


def compute_trajectory(history: Sequence[dict]) -> dict:
    """`history` newest-first. Returns {quarters:[labels oldest→newest], metrics:{
    key:{label, kind, current, qoq, yoy, sparkline, inflection, inflection_note}}}."""
    hist = list(history or [])
    asc = list(reversed(hist))                      # oldest → newest for sparklines
    labels = [q.get("period_label") or q.get("period_end") for q in asc]
    out_metrics: dict[str, dict] = {}
    for key, label, kind in METRICS:
        series = [q.get(key) for q in asc]
        cur = hist[0].get(key) if hist else None
        prev = hist[1].get(key) if len(hist) > 1 else None
        yoy_ref = hist[4].get(key) if len(hist) > 4 else None
        infl, note = _inflection(key, cur, prev, series)
        out_metrics[key] = {
            "label": label, "kind": kind, "current": cur,
            "qoq": _delta(cur, prev, kind), "yoy": _delta(cur, yoy_ref, kind),
            "sparkline": series, "inflection": infl, "inflection_note": note,
        }
    return {"quarters": labels, "metrics": out_metrics, "n": len(hist)}


def _inflection(key: str, cur: float | None, prev: float | None,
                series: Sequence[float | None]) -> tuple[bool, str | None]:
    """Flag a turn worth reading: a margin/FCF that FLIPS sign QoQ, or debt that
    ACCELERATES (this quarter's rise bigger than the prior one)."""
    if cur is None or prev is None:
        return False, None
    if key in ("gross_margin", "operating_margin", "net_margin", "fcf", "net_income", "eps"):
        if (prev >= 0 > cur) :
            return True, "è passato in negativo"
        if (prev < 0 <= cur):
            return True, "è tornato positivo"
    if key == "debt":
        vals = [v for v in series if v is not None]
        if len(vals) >= 3:
            d_now = vals[-1] - vals[-2]
            d_prev = vals[-2] - vals[-3]
            if d_now > 0 and d_prev > 0 and d_now > 1.5 * d_prev:
                return True, "il debito sta accelerando"
    return False, None


def own_percentile(values: Sequence[float | None], current: float | None,
                   *, min_n: int = 8) -> dict:
    """Percentile of `current` within its own accumulated history (e.g. P/E over
    time). Needs >= min_n points; else n reported, percentile None. Descriptive."""
    hist = [v for v in values if v is not None and v > 0]
    if current is None or current <= 0:
        return {"percentile": None, "n": len(hist), "band": "n/d"}
    if len(hist) < min_n:
        return {"percentile": None, "n": len(hist), "band": "storia insufficiente"}
    pctl = sum(1 for v in hist if v <= current) / len(hist)
    band = "cara" if pctl >= 0.66 else "economica" if pctl <= 0.34 else "nella media"
    return {"percentile": pctl, "n": len(hist), "band": band}

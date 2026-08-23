"""Calibration metrics — is the model honest about its own uncertainty?

The piece that makes probabilistic output serious: check DECLARED vs REALISED.
  * reliability diagram — of the times we said "X% chance below level", did it
    happen ~X% of the time? (bucketed)
  * Brier score — mean squared error of probabilistic calls (0 = perfect).
  * interval coverage — does the stated 68% interval actually contain the outcome
    68% of the time? the 95% 95%?

Constrained recalibration (recalibrate_dispersion): find a single volatility/width
SCALE factor that fixes systematic over/under-confidence, estimate it on one period
and KEEP it only if it improves coverage OUT-OF-SAMPLE. It NEVER shifts direction
(no "was too high → push down" — that's chasing noise). Pure; tested.
"""
from __future__ import annotations

from collections.abc import Sequence


# --- reliability diagram --------------------------------------------
def reliability(predictions: Sequence[tuple[float, bool]], *, bins: int = 10) -> list[dict]:
    """`predictions` = [(declared_prob, event_happened)]. Bucket by declared prob;
    each bucket returns declared-mean vs realised-frequency + n."""
    buckets: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for p, hit in predictions:
        idx = min(bins - 1, max(0, int(p * bins)))
        buckets[idx].append((p, bool(hit)))
    out = []
    for i, b in enumerate(buckets):
        if not b:
            out.append({"bin": i, "n": 0, "declared": None, "realised": None})
            continue
        out.append({"bin": i, "n": len(b),
                    "declared": sum(p for p, _ in b) / len(b),
                    "realised": sum(1 for _, h in b if h) / len(b)})
    return out


def brier_score(predictions: Sequence[tuple[float, bool]]) -> float | None:
    """Mean (p − outcome)². Lower is better; 0 is perfect."""
    preds = list(predictions)
    if not preds:
        return None
    return sum((p - (1.0 if hit else 0.0)) ** 2 for p, hit in preds) / len(preds)


# --- interval coverage ----------------------------------------------
def interval_coverage(intervals: Sequence[tuple[float, float, float]]) -> dict:
    """`intervals` = [(low, high, outcome)]. Fraction where low ≤ outcome ≤ high."""
    items = list(intervals)
    if not items:
        return {"n": 0, "coverage": None}
    inside = sum(1 for lo, hi, x in items if lo <= x <= hi)
    return {"n": len(items), "coverage": inside / len(items)}


def coverage_report(records: Sequence[dict]) -> dict:
    """From forecast records with realised outcome, the 68% and 95% coverage +
    a plain verdict when a band is systematically wrong."""
    c68 = interval_coverage([(r["p16"], r["p84"], r["outcome"]) for r in records
                             if all(k in r for k in ("p16", "p84", "outcome"))])
    c95 = interval_coverage([(r["p2_5"], r["p97_5"], r["outcome"]) for r in records
                             if all(k in r for k in ("p2_5", "p97_5", "outcome"))])
    verdict = None
    if c95["coverage"] is not None and c95["n"] >= 10:
        if c95["coverage"] < 0.85:
            verdict = (f"sovra-sicuro: intervallo 95% reale {c95['coverage'] * 100:.0f}% "
                       "(troppo stretto) — allarga l'incertezza")
        elif c95["coverage"] > 0.99:
            verdict = (f"sotto-sicuro: intervallo 95% reale {c95['coverage'] * 100:.0f}% "
                       "(troppo largo)")
    return {"coverage_68": c68, "coverage_95": c95, "verdict": verdict}


# --- constrained recalibration (dispersion only) --------------------
def _scaled_coverage(records: Sequence[dict], scale: float, band: str) -> float | None:
    """Coverage after widening each interval around its median by `scale`."""
    lo_k, hi_k = ("p16", "p84") if band == "68" else ("p2_5", "p97_5")
    items = []
    for r in records:
        if not all(k in r for k in (lo_k, hi_k, "median", "outcome")):
            continue
        m = r["median"]
        lo = m + (r[lo_k] - m) * scale
        hi = m + (r[hi_k] - m) * scale
        items.append((lo, hi, r["outcome"]))
    return interval_coverage(items)["coverage"] if items else None


def recalibrate_dispersion(train: Sequence[dict], test: Sequence[dict], *,
                           band: str = "95", target: float = 0.95,
                           scales: Sequence[float] | None = None) -> dict:
    """Find the width SCALE (on `train`) that best hits `target` coverage, then
    KEEP it only if it improves coverage on `test` (out-of-sample). Direction is
    never touched — only the interval width around the unchanged median."""
    scales = scales or [round(0.6 + 0.1 * i, 2) for i in range(25)]   # 0.6 .. 3.0
    base_train = _scaled_coverage(train, 1.0, band)
    base_test = _scaled_coverage(test, 1.0, band)
    if base_train is None or base_test is None:
        return {"applied": False, "reason": "dati insufficienti per la ricalibrazione"}
    best = min(scales, key=lambda s: abs((_scaled_coverage(train, s, band) or 0) - target))
    new_test = _scaled_coverage(test, best, band)
    improves = new_test is not None and abs(new_test - target) < abs(base_test - target) - 1e-9
    return {
        "applied": bool(improves and abs(best - 1.0) > 1e-9),
        "scale": best, "band": band, "target": target,
        "train_coverage_before": base_train, "test_coverage_before": base_test,
        "test_coverage_after": new_test,
        "reason": ("migliora fuori campione: applicata (solo dispersione, non direzione)"
                   if improves else
                   "NON migliora fuori campione: non applicata (evita di inseguire rumore)"),
    }

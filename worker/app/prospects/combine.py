"""Combined distribution — options + conditional history + calibrated factor tilt.

The main result of the Prospettive engine: for one instrument × horizon, blend the
component distributions into ONE, with weights DETERMINED BY THE TRACK RECORD (per
-component calibration), not fixed by hand. Legitimate because the weights come
from measured Brier/coverage and the combined is ADOPTED only where it beats the
best single component out-of-sample; elsewhere the best component is used and
declared.

Everything is in RETURN space (proxy-safe). Distributions are moment-matched to a
normal (mean = median, sd from the 68% band); the combination uses the law of
total variance for a mixture, so the combined width honestly widens when the
components disagree. Every derived scalar (P(up), median, P(above level)) is
returned WITH the interval, never alone. PURE; tested in test_prospects_combine.py.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

Z68, Z95 = 0.9944578832097535, 1.959963984540054   # z for 68.27% / 95% two-sided
FACTOR_TILT_CAP = 0.02   # a factor tilt can shift the mean at most ±2% (bounded)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def to_normal(dist: Mapping) -> tuple[float, float] | None:
    """(mean, sd) from a component's return summary (median + 68% band). None if
    the band is missing/degenerate."""
    if not dist:
        return None
    m = dist.get("median")
    p16, p84 = dist.get("p16"), dist.get("p84")
    if m is None or p16 is None or p84 is None:
        return None
    sd = (p84 - p16) / 2.0
    if sd <= 0:
        return None
    return (float(m), float(sd))


def component_weights(cal_by_component: Mapping[str, Mapping]) -> dict:
    """Weights ∝ calibration quality. Prefer lower Brier; else coverage-closeness
    to nominal (95%); else equal. `cal_by_component` maps name -> {brier?, coverage_95?}.
    Only components present in the mapping get a weight."""
    names = list(cal_by_component)
    if not names:
        return {}
    scores = {}
    for n in names:
        c = cal_by_component[n] or {}
        if c.get("brier") is not None and c["brier"] > 0:
            scores[n] = 1.0 / c["brier"]
        elif c.get("coverage_95") is not None:
            scores[n] = max(1e-3, 1.0 - abs(c["coverage_95"] - 0.95))
        else:
            scores[n] = 1.0                       # no track record -> equal
    total = sum(scores.values()) or 1.0
    return {n: scores[n] / total for n in names}


def factor_tilt(factors: Sequence[Mapping], *, scale: float = 0.5) -> dict:
    """Mean shift from CALIBRATED factors: only significant, non-contrary factors
    at this horizon contribute. shift = Σ ic·scale, capped at ±FACTOR_TILT_CAP.
    `factors` = [{key, ic, significant, contrary}]. Contrary/insignificant ignored."""
    used = [f for f in factors if f.get("significant") and not f.get("contrary")
            and f.get("ic") is not None]
    raw = sum(float(f["ic"]) * scale for f in used)
    shift = max(-FACTOR_TILT_CAP, min(FACTOR_TILT_CAP, raw))
    return {"shift": shift, "factors_used": [f.get("key") for f in used],
            "capped": abs(raw) > FACTOR_TILT_CAP}


def combine(components: Mapping[str, Mapping], weights: Mapping[str, float],
            *, tilt: float = 0.0, level_ret: float | None = None) -> dict:
    """Moment-matched mixture of the given components (return space).

    combined_mean = Σ wᵢ μᵢ (+ tilt);  combined_var = Σ wᵢ(σᵢ²+μᵢ²) − mean₀²
    (law of total variance → width grows when components disagree). Returns median
    + 68/95 bands + P(up) + optional P(above level), each WITH the width."""
    parts = []
    for name, w in weights.items():
        mn = to_normal(components.get(name))
        if mn and w > 0:
            parts.append((name, w, mn[0], mn[1]))
    if not parts:
        return {"available": False, "note": "nessuna componente disponibile per il combinato"}
    wsum = sum(w for _, w, _, _ in parts)
    parts = [(n, w / wsum, mu, sd) for n, w, mu, sd in parts]
    mean0 = sum(w * mu for _, w, mu, _ in parts)                 # pre-tilt mean
    ex2 = sum(w * (sd * sd + mu * mu) for _, w, mu, sd in parts)
    var = max(ex2 - mean0 * mean0, 1e-12)
    sd = math.sqrt(var)
    mean = mean0 + tilt
    out = {
        "available": True,
        "median": mean,
        "p16": mean - Z68 * sd, "p84": mean + Z68 * sd,
        "p2_5": mean - Z95 * sd, "p97_5": mean + Z95 * sd,
        "sd": sd,
        "prob_up": 1.0 - _norm_cdf((0.0 - mean) / sd),
        "weights": {n: round(w, 4) for n, w, _, _ in parts},
        "tilt": tilt,
        "note": "Combinato moment-matched (media pesata, varianza di mistura). Ogni numero va letto con l'ampiezza accanto.",
    }
    if level_ret is not None:
        out["prob_above"] = 1.0 - _norm_cdf((level_ret - mean) / sd)
        out["level_ret"] = level_ret
    return out


def adopt_combined(combined_score: float | None, best_component_score: float | None,
                   best_component_name: str | None) -> dict:
    """Adopt the combined ONLY if its OOS score (Brier, lower=better) beats the
    best single component. Otherwise fall back to that component, declared."""
    if combined_score is None or best_component_score is None:
        return {"use": "combined", "validated": False,
                "reason": "track record insufficiente per validare OOS: combinato mostrato non validato"}
    if combined_score < best_component_score - 1e-9:
        return {"use": "combined", "validated": True,
                "reason": f"il combinato batte la miglior componente OOS (Brier {combined_score:.3f} < {best_component_score:.3f})"}
    return {"use": best_component_name or "options", "validated": True,
            "reason": (f"il combinato NON batte «{best_component_name}» OOS "
                       f"(Brier {combined_score:.3f} ≥ {best_component_score:.3f}): uso la componente migliore")}

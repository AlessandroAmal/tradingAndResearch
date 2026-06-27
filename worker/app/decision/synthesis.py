"""Confluence read — TRANSPARENT, testable synthesis of the board's signals.

Takes the signals the board already collected and, for EACH factor, classifies
it bullish / bearish / neutral FOR THE INSTRUMENT, with a configurable weight,
then aggregates into a directional LEAN on a -100..+100 scale with a qualitative
label.

HARD HONESTY RULES (CLAUDE.md §1, §5) — enforced here, not just in the UI:
  * The lean is the ALIGNMENT OF CURRENT CONDITIONS, NOT a probability and NOT a
    forecast of the next move. Every result says so (`disclaimer`).
  * It is NEVER expressed as a directional probability. There is deliberately NO
    "X% up/down" field anywhere in the output. The ONLY probability shown by the
    cockpit is the option-IMPLIED one (M9), passed through verbatim as the
    market's odds.
  * Every factor's contribution is always exposed (full transparency).
  * Missing data → the factor is EXCLUDED (never guessed) and listed in
    `excluded`.
  * Inherently non-directional context (ATR/volatility regime, event risk,
    streak) never feeds the lean — it is shown as `kind: "context"`.

Mapping for gold is explicit and comes from known relationships; macro drivers
reuse their configured `supportive_when` (already on each driver), so the same
engine generalises to any instrument by editing config only.

Tested in `worker/tests/test_synthesis.py` (FRED/yfinance mocked).
"""
from __future__ import annotations

from collections.abc import Mapping

from ..technicals import plural_days

BULLISH, BEARISH, NEUTRAL = "bullish", "bearish", "neutral"

# Context factors never contribute to the directional lean, regardless of any
# configured weight — they are genuinely non-directional.
_CONTEXT_ONLY = {"streak", "atr", "event_risk"}

# Default weights (configurable per instrument under decision_board.*.synthesis).
DEFAULT_WEIGHTS = {
    "trend_ma": 1.0,
    "rsi": 0.0,          # stretch context — off by default (avoids mean-reversion fallacy)
    "streak": 0.0,       # context only
    "atr": 0.0,          # context only
    "event_risk": 0.0,   # caution flag, never directional
}

CAVEATS = [
    "Fotografia delle condizioni ATTUALI, non una previsione del prossimo movimento.",
    "I singoli fattori sono deboli e dipendono dal regime di mercato.",
    "La probabilità del futuro è solo quella IMPLICITA nei prezzi delle opzioni (sotto): gli odds del mercato, non una profezia.",
]

LEAN_DISCLAIMER = (
    "Lettura = allineamento delle condizioni attuali, NON una probabilità né una "
    "previsione. Non è una percentuale di salita/discesa."
)


def _score_of(classification: str) -> int:
    return {BULLISH: 1, BEARISH: -1}.get(classification, 0)


# --- macro state: LEVEL/REGIME + daily direction ---------------------
# A driver is classified by where its level sits in its own history (regime),
# not only by today's move. e.g. a real yield that is high-but-falling is still
# a structural headwind for gold, not simply "favorable" because it ticked down.
def _to_wind(classification: str) -> str:
    return {BULLISH: "tailwind", BEARISH: "headwind"}.get(classification, "neutral")


def regime_label(percentile: float | None, high_pct: float, low_pct: float) -> str:
    if percentile is None:
        return "n/d"
    if percentile >= high_pct:
        return "high"
    if percentile <= low_pct:
        return "low"
    return "mid"


def _regime_class(supportive_when: str | None, percentile: float | None,
                  high_pct: float, low_pct: float) -> str:
    if percentile is None or not supportive_when:
        return NEUTRAL
    lab = regime_label(percentile, high_pct, low_pct)
    if lab == "mid":
        return NEUTRAL
    low_is_good = supportive_when == "falling"  # low level supports the instrument
    if lab == "low":
        return BULLISH if low_is_good else BEARISH
    return BEARISH if low_is_good else BULLISH   # high level


def _move_class(direction: str | None, supportive_when: str | None) -> str:
    if not supportive_when or direction == "flat" or not direction:
        return NEUTRAL
    good = "up" if supportive_when == "rising" else "down"
    return BULLISH if direction == good else BEARISH


def classify_macro_state(
    supportive_when: str | None,
    direction: str | None,
    percentile: float | None,
    *,
    high_pct: float = 0.66,
    low_pct: float = 0.34,
    use_regime: bool = True,
) -> dict:
    """Combine level/regime and daily direction into a state for the instrument.

    When `use_regime` and the level is at an extreme, the REGIME drives the state
    (structural); otherwise the daily move does. Returns both so the UI can show
    level AND movement. `state` is the tailwind/headwind/neutral display label;
    `classification` is the bullish/bearish/neutral used by the lean.
    """
    move = _move_class(direction, supportive_when)
    regime_cls = _regime_class(supportive_when, percentile, high_pct, low_pct)
    cls = regime_cls if (use_regime and regime_cls != NEUTRAL) else move
    return {
        "state": _to_wind(cls),
        "classification": cls,
        "regime": regime_label(percentile, high_pct, low_pct),
        "regime_class": regime_cls,
        "move_class": move,
    }


# --- per-factor classifiers ------------------------------------------
def _macro_factor(driver: Mapping) -> dict:
    """Reuse the driver's context state: tailwind = bullish, headwind = bearish.
    The state already encodes `supportive_when` for the instrument."""
    sid = driver.get("id")
    key = f"macro:{sid}"
    label = driver.get("label", sid)
    weight = float(driver.get("weight", 1.0))
    if driver.get("value") is None:
        return _excluded(key, label, weight, "dato macro mancante")
    # Prefer the regime-aware classification computed at board time; fall back to
    # deriving it from the display state for older snapshots.
    cls = driver.get("classification")
    if cls not in (BULLISH, BEARISH, NEUTRAL):
        cls = {"tailwind": BULLISH, "headwind": BEARISH}.get(driver.get("state"), NEUTRAL)
    arrow = {"up": "↑", "down": "↓", "flat": "→"}.get(driver.get("direction"), "→")
    regime = driver.get("regime")
    regime_txt = f" · livello {regime}" if regime and regime != "n/d" else ""
    return _factor(key, label, cls, weight, kind="directional",
                   detail=f"{arrow}{regime_txt} {driver.get('interpretation') or ''}".strip())


def _trend_factor(technicals: Mapping, weight: float) -> dict:
    """Bullish if above a RISING MA200; bearish if below a FALLING MA50; else neutral."""
    key, label = "trend_ma", "Trend (MA200/MA50)"
    mas = {m.get("period"): m for m in technicals.get("ma", [])}
    ma200, ma50 = mas.get(200), mas.get(50)
    if not ma200 or ma200.get("above") is None:
        return _excluded(key, label, weight, "MA200 non disponibile")
    above200, rising200 = ma200.get("above"), ma200.get("rising")
    below50 = (ma50 or {}).get("above") is False
    falling50 = (ma50 or {}).get("rising") is False
    if above200 and rising200:
        return _factor(key, label, BULLISH, weight, kind="directional",
                       detail="prezzo sopra una MA200 in salita (trend rialzista)")
    if below50 and falling50:
        return _factor(key, label, BEARISH, weight, kind="directional",
                       detail="prezzo sotto una MA50 in discesa (trend ribassista)")
    pos = "sopra" if above200 else "sotto"
    return _factor(key, label, NEUTRAL, weight, kind="directional",
                   detail=f"{pos} MA200, pendenza non conferma un trend netto")


def _rsi_factor(technicals: Mapping, weight: float) -> dict:
    """RSI stretch as low-weight context. Off by default (weight 0)."""
    key, label = "rsi", "RSI (stiramento)"
    rsi = technicals.get("rsi", {})
    val, zone = rsi.get("value"), rsi.get("zone")
    if val is None:
        return _excluded(key, label, weight, "RSI non disponibile")
    # Stretch reading (mean-reversion) ONLY when explicitly weighted in.
    cls = NEUTRAL
    if weight > 0:
        cls = {"overbought": BEARISH, "oversold": BULLISH}.get(zone, NEUTRAL)
    kind = "directional" if weight > 0 else "context"
    return _factor(key, label, cls, weight, kind=kind,
                   detail=f"RSI {val:.0f} · {zone} (soglie {rsi.get('oversold')}/{rsi.get('overbought')})")


def _streak_factor(technicals: Mapping) -> dict:
    sk = technicals.get("streak", {})
    n, d = sk.get("length", 0), sk.get("direction")
    detail = (f"{n} {plural_days(n)} {'su' if d == 'up' else 'giù'} (momentum, non direzione futura)"
              if n else "nessuno streak in corso")
    return _factor("streak", "Streak / momentum", NEUTRAL, 0.0, kind="context", detail=detail)


def _atr_factor(technicals: Mapping) -> dict:
    atr_pct = technicals.get("atr_pct")
    detail = (f"ATR ≈ {atr_pct:.1f}% del prezzo (regime di volatilità)"
              if atr_pct is not None else "volatilità non disponibile")
    return _factor("atr", "ATR / volatilità", NEUTRAL, 0.0, kind="context", detail=detail)


def _event_factor(next_event: Mapping | None) -> dict:
    if not next_event:
        return _factor("event_risk", "Rischio evento", NEUTRAL, 0.0, kind="context",
                       detail="nessun catalizzatore imminente")
    # A caution flag, NOT a direction.
    return _factor("event_risk", "Rischio evento", "caution", 0.0, kind="context",
                   detail=f"{next_event.get('title')} ({next_event.get('event_time')}) — cautela, non direzione")


# --- factory helpers -------------------------------------------------
def _factor(key, label, classification, weight, *, kind, detail) -> dict:
    return {
        "key": key, "label": label, "classification": classification,
        "weight": float(weight), "kind": kind, "included": True, "detail": detail,
    }


def _excluded(key, label, weight, reason) -> dict:
    return {
        "key": key, "label": label, "classification": NEUTRAL,
        "weight": float(weight), "kind": "directional", "included": False,
        "detail": f"escluso: {reason}",
    }


# --- lean label ------------------------------------------------------
def _label(score: float | None) -> tuple[str, str]:
    if score is None:
        return "dati insufficienti", NEUTRAL
    direction = BULLISH if score > 0 else BEARISH if score < 0 else NEUTRAL
    word = {"bullish": "rialzista", "bearish": "ribassista"}.get(direction)
    mag = abs(score)
    if mag < 15 or direction == NEUTRAL:
        return "neutrale / condizioni miste", NEUTRAL
    if mag < 40:
        return f"leggermente {word}", direction
    if mag < 70:
        return f"moderatamente {word}", direction
    return f"fortemente {word}", direction


# --- market comparison (vs option-implied odds) ----------------------
def _market_lean(implied: Mapping | None) -> dict:
    """Reduce the implied probabilities to a coarse market lean for comparison.
    The implied probability is the ONLY probability — passed through untouched."""
    horizons = [h for h in (implied or {}).get("horizons", []) if h.get("available")]
    if not horizons:
        return {"direction": None, "prob_up": None, "horizon": None,
                "note": "Probabilità implicite non disponibili."}
    # Use the longest available horizon (most informative for a 'lean').
    h = max(horizons, key=lambda x: x.get("days_to_expiry", 0))
    p = h.get("prob_up")
    direction = NEUTRAL
    if p is not None:
        direction = BULLISH if p > 0.55 else BEARISH if p < 0.45 else NEUTRAL
    return {"direction": direction, "prob_up": p,
            "horizon": h.get("target_days"), "days_to_expiry": h.get("days_to_expiry")}


def _divergence(lean_dir: str, market: Mapping) -> dict:
    md = market.get("direction")
    if md is None:
        return {"level": "unknown",
                "message": "Probabilità di mercato non disponibili per il confronto."}
    it = {"bullish": "rialziste", "bearish": "ribassiste", "neutral": "miste"}
    itm = {"bullish": "rialzisti", "bearish": "ribassisti", "neutral": "~neutri"}
    if lean_dir == NEUTRAL:
        return {"level": "aligned" if md == NEUTRAL else "mild",
                "message": f"Condizioni {it[lean_dir]}; gli odds di mercato sono {itm[md]}."}
    if md == lean_dir:
        return {"level": "aligned",
                "message": f"Condizioni {it[lean_dir]} e mercato {itm[md]}: allineati."}
    if md == NEUTRAL:
        move = "ribasso" if lean_dir == BEARISH else "rialzo"
        return {"level": "notable",
                "message": (f"Condizioni {it[lean_dir]} ma mercato {itm[md]} → "
                            f"possibile che il {move} sia già prezzato.")}
    return {"level": "notable",
            "message": (f"Condizioni {it[lean_dir]} ma odds di mercato {itm[md]} → "
                        f"tensione: il mercato prezza diversamente.")}


# --- main entry ------------------------------------------------------
def confluence_read(
    *,
    drivers: list[Mapping],
    technicals: Mapping,
    implied: Mapping | None,
    next_event: Mapping | None,
    weights: Mapping | None = None,
) -> dict:
    """Build the transparent confluence read. Pure: no I/O."""
    w = {**DEFAULT_WEIGHTS, **dict(weights or {})}

    factors: list[dict] = []
    for d in drivers or []:
        factors.append(_macro_factor(d))
    factors.append(_trend_factor(technicals or {}, float(w.get("trend_ma", 1.0))))
    factors.append(_rsi_factor(technicals or {}, float(w.get("rsi", 0.0))))
    factors.append(_streak_factor(technicals or {}))
    factors.append(_atr_factor(technicals or {}))
    factors.append(_event_factor(next_event))

    # Lean: weighted mean of {-1,0,+1} over INCLUDED, weighted, directional,
    # NON-context factors. Context factors never contribute (no fabricated direction).
    contributing = [
        f for f in factors
        if f["included"] and f["kind"] == "directional"
        and f["key"] not in _CONTEXT_ONLY and f["weight"] > 0
    ]
    total_w = sum(f["weight"] for f in contributing)
    score = None
    if total_w > 0:
        raw = sum(_score_of(f["classification"]) * f["weight"] for f in contributing)
        score = round(100.0 * raw / total_w, 1)

    label, direction = _label(score)
    excluded = [f["key"] for f in factors if not f["included"]]
    market = _market_lean(implied)

    return {
        "lean": {
            "score": score,                 # -100..+100 magnitude, NOT a probability
            "label": label,
            "direction": direction,
            "contributing_factors": len(contributing),
            "disclaimer": LEAN_DISCLAIMER,
        },
        "factors": factors,
        "excluded": excluded,
        "market": market,                   # coarse lean derived from the implied odds
        "divergence": _divergence(direction, market),
        "caveats": CAVEATS,
    }

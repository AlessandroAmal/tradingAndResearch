"""Option-implied probabilities at multiple horizons — the market's odds.

Reuses the options desk (Black-Scholes / IV solver in `app.options`) on the
gold proxy ETF GLD. From option chains at different expiries we derive, per
horizon (~1 day / ~3 days / ~1 month):
  - the expected move (±1σ, from ATM implied vol over the horizon), and
  - the RISK-NEUTRAL probability the underlying finishes ABOVE / BELOW a level
    (default: the current spot) — i.e. the "probability it rises" reference.

These are probabilities IMPLIED BY OPTION PRICES (the market's odds), NOT a
forecast — labelled as such everywhere they surface (CLAUDE.md §5).

The provider is the existing OptionsProvider, so this is unit-tested with a
mocked provider (no network) in `worker/tests/test_decision_board.py`.
"""
from __future__ import annotations

import math
from datetime import date

from .. import options as opt
from ..logging_setup import get_logger
from ..providers.options import OptionsProvider

log = get_logger("decision.implied")


def _mid(q) -> float | None:
    if q.bid and q.ask and q.bid > 0 and q.ask > 0:
        return (q.bid + q.ask) / 2.0
    return q.last if (q.last and q.last > 0) else None


def _atm_iv(quotes, spot: float, T: float, r: float) -> float | None:
    """Recompute ATM implied vol: average of call & put IV at the strike
    nearest spot (Yahoo's IV is ignored — see app.options)."""
    strikes = sorted({q.strike for q in quotes})
    if not strikes:
        return None
    atm = min(strikes, key=lambda s: abs(s - spot))
    ivs: list[float] = []
    for q in quotes:
        if q.strike != atm:
            continue
        m = _mid(q)
        if not m:
            continue
        iv = opt.implied_vol(q.option_type, m, spot, q.strike, T, r)
        if iv:
            ivs.append(iv)
    return sum(ivs) / len(ivs) if ivs else None


def _pick_expiry(expiries: list[str], today: date, target_days: int) -> tuple[str, int] | None:
    """Expiry whose days-to-expiry is closest to `target_days` (must be > 0)."""
    candidates = []
    for e in expiries:
        try:
            d = (date.fromisoformat(e[:10]) - today).days
        except ValueError:
            continue
        if d > 0:
            candidates.append((e, d))
    if not candidates:
        return None
    return min(candidates, key=lambda c: abs(c[1] - target_days))


def implied_probabilities(
    provider: OptionsProvider,
    underlying: str,
    *,
    today: date,
    horizons_days: list[int],
    r: float,
    level: float | None = None,
) -> dict:
    """Return implied (risk-neutral) probabilities for `underlying` per horizon.

    `level` defaults to the current spot (P(finish above current price)).
    Degrades gracefully: if the underlying has no options, returns a result with
    an explanatory note and no horizons.
    """
    spot = provider.get_spot(underlying)
    if not spot:
        return {"underlying": underlying, "spot": None, "level": level,
                "horizons": [], "note": "Nessun prezzo per il sottostante."}

    try:
        expiries = provider.list_expiries(underlying)
    except Exception as exc:  # noqa: BLE001 — degrade gracefully
        log.warning("Implied probs: expiries failed for %s: %s", underlying, exc)
        expiries = []
    if not expiries:
        return {"underlying": underlying, "spot": spot, "level": level or spot,
                "horizons": [], "note": "Nessuna catena opzioni disponibile."}

    lvl = level if level else spot
    chain_cache: dict[str, list] = {}
    horizons: list[dict] = []

    for target in horizons_days:
        pick = _pick_expiry(expiries, today, target)
        if not pick:
            horizons.append({"target_days": target, "available": False,
                             "note": "Nessuna scadenza utile."})
            continue
        expiry, dte = pick
        if expiry not in chain_cache:
            try:
                chain_cache[expiry] = provider.fetch_chain(underlying, expiry)
            except Exception as exc:  # noqa: BLE001
                log.warning("Implied probs: chain failed %s %s: %s", underlying, expiry, exc)
                chain_cache[expiry] = []
        quotes = chain_cache[expiry]
        T = max(dte, 0) / 365.0
        iv = _atm_iv(quotes, spot, T, r) if quotes else None
        if not iv or T <= 0:
            horizons.append({"target_days": target, "expiry": expiry,
                             "days_to_expiry": dte, "available": False,
                             "note": "IV ATM non calcolabile (liquidità?)."})
            continue
        exp_move = iv * math.sqrt(T)          # ±1σ, decimal
        prob_up = opt.prob_above(spot, lvl, T, r, iv)
        prob_down = None if prob_up is None else 1.0 - prob_up
        horizons.append({
            "target_days": target,
            "expiry": expiry,
            "days_to_expiry": dte,
            "available": True,
            "atm_iv": iv,
            "expected_move_pct": exp_move * 100.0,
            "expected_move_abs": exp_move * spot,
            "prob_up": prob_up,        # P(finish above level) — market odds
            "prob_down": prob_down,
        })

    return {
        "underlying": underlying,
        "spot": spot,
        "level": lvl,
        "risk_free_rate": r,
        "horizons": horizons,
        "note": "Probabilità implicite nei prezzi delle opzioni (odds del mercato), NON una previsione.",
    }

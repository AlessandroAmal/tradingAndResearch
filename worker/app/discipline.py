"""Discipline trackers — profit set-aside, committed-budget windows, and the
2/3 profit-giveback exit guide. PURE & TESTED (`worker/tests/test_discipline.py`).

READ-ONLY reminders built from the user's OWN rules and realised numbers. Nothing
here moves money, places an order, or predicts price. The 2/3 guide is a nudge
based on the user's rule ("when profit falls to ~2/3 of its peak, consider taking
some"), NOT a forecast.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

from . import risk as risk_math

TWO_THIRDS = 2.0 / 3.0


def _as_date(v) -> date | None:
    if v is None:
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


# --- profit set-aside tracker (#4) -----------------------------------
def set_aside_today(closed_trades: Sequence[Mapping], target: float,
                    today: date) -> dict:
    """From trades CLOSED today in profit, how much to set aside (reminder only).

    `closed_trades` = [{realized_pnl, closed_at}]. set_aside = min(profit, target).
    """
    realized = 0.0
    for t in closed_trades or ():
        if _as_date(t.get("closed_at")) != today:
            continue
        pnl = t.get("realized_pnl")
        if pnl is not None and pnl > 0:
            realized += float(pnl)
    set_aside = min(realized, float(target)) if realized > 0 else 0.0
    return {"realized_profit": realized, "set_aside": set_aside, "target": float(target)}


# --- committed-budget windows (#1) -----------------------------------
def _in_window(opened: date | None, today: date, window: str) -> bool:
    if opened is None:
        return False
    if window == "day":
        return opened == today
    if window == "week":
        return opened.isocalendar()[:2] == today.isocalendar()[:2]
    if window == "month":
        return (opened.year, opened.month) == (today.year, today.month)
    return False


def committed_in_windows(open_positions: Sequence[Mapping], today: date) -> dict:
    """Sum of open RISK (entry→stop, real point value) of REAL open positions,
    grouped by the window their `opened_at` falls in. Paper excluded by caller."""
    out = {"day": 0.0, "week": 0.0, "month": 0.0}
    for p in open_positions or ():
        r = risk_math.open_risk(
            float(p.get("entry") or 0.0),
            None if p.get("stop") in (None, "") else float(p["stop"]),
            float(p.get("size") or 0.0),
            float(p.get("multiplier") or 1.0),
        )
        if r is None:
            continue
        opened = _as_date(p.get("opened_at"))
        for win in out:
            if _in_window(opened, today, win):
                out[win] += r
    return out


# --- 2/3 profit-giveback exit guide (#6) -----------------------------
def max_favorable_excursion(side: str, entry: float, size: float, multiplier: float,
                            highs: Sequence[float], lows: Sequence[float]) -> float:
    """Peak UNREALISED profit reached since entry (0 if it never went favourable).

    Long: best high above entry; short: best low below entry. Uses the correct
    point value so the peak P&L is in currency."""
    if side == "long":
        best = max((h for h in highs or ()), default=None)
        move = (best - entry) if best is not None else 0.0
    else:
        best = min((low for low in lows or ()), default=None)
        move = (entry - best) if best is not None else 0.0
    peak = move * float(size) * float(multiplier)
    return max(peak, 0.0)


def two_thirds_trigger(peak_pnl: float | None, current_pnl: float | None,
                       scale: float = TWO_THIRDS) -> bool:
    """True when profit has given back to/under `scale` of a POSITIVE peak."""
    if peak_pnl is None or peak_pnl <= 0 or current_pnl is None:
        return False
    return current_pnl <= scale * peak_pnl


def exit_guide(side: str, entry: float, size: float, multiplier: float,
               highs: Sequence[float], lows: Sequence[float],
               current_pnl: float | None, scale: float = TWO_THIRDS) -> dict:
    """Peak P&L + whether the 2/3 give-back guide has triggered. A nudge, not a
    prediction."""
    peak = max_favorable_excursion(side, entry, size, multiplier, highs, lows)
    triggered = two_thirds_trigger(peak, current_pnl, scale)
    return {
        "peak_pnl": peak,
        "threshold_pnl": scale * peak if peak > 0 else None,
        "triggered": triggered,
        "note": ("Profitto sceso sotto la soglia 2/3 del picco: valuta di prendere "
                 "(guida basata sulla TUA regola, non una previsione)." if triggered else None),
    }

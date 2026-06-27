"""FX desk signals — what currency desks actually watch, all REAL and labelled.

Every number here is either priced by the market (option skew / expected move) or
measured from data (historical event behaviour) — never a fabricated directional
probability (CLAUDE.md). Each signal carries what it IS and its uncertainty.

  * risk_reversal  — 25Δ IV(put) − IV(call) from the (FXE) smile: where flows /
    hedging concentrate. RR>0 = put bias (lean bearish); RR<0 = call bias
    (lean bullish). NOT a forecast. Thin smile → low reliability.
  * expected_move_on_events — ±% the option term structure prices into the expiry
    spanning the next FOMC/ECB/CPI/NFP. Magnitude, not direction.
  * event_behaviour — for PAST events of the same type: median absolute day move,
    and how often the first move continued vs reversed. Frequency, with n always.
  * positioning_state — COT percentile → crowded-long (reversal risk) /
    crowded-short (squeeze risk) only at the extremes.

Pure functions; the option-price→(delta,iv) extraction reuses `app.options`.
Tested in `worker/tests/test_fx_signals.py`.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from .. import options as opt


# --- 25-delta interpolation + risk reversal --------------------------
def interp_y(points: Sequence[tuple[float, float]], x: float) -> tuple[float | None, bool]:
    """Linear interpolation of y at x over (x,y) points. Returns (y, extrapolated).
    y is None if there are <2 points; `extrapolated` True if x is outside range."""
    pts = sorted((p for p in points if p[0] is not None and p[1] is not None), key=lambda p: p[0])
    if len(pts) < 2:
        return None, True
    xs = [p[0] for p in pts]
    if x <= xs[0]:
        return pts[0][1], x < xs[0]
    if x >= xs[-1]:
        return pts[-1][1], x > xs[-1]
    for i in range(1, len(pts)):
        if pts[i][0] >= x:
            x0, y0 = pts[i - 1]
            x1, y1 = pts[i]
            w = (x - x0) / (x1 - x0) if x1 != x0 else 0.0
            return y0 + w * (y1 - y0), False
    return pts[-1][1], False


def risk_reversal(call_points: Sequence[tuple[float, float]],
                  put_points: Sequence[tuple[float, float]],
                  *, target_delta: float = 0.25) -> dict:
    """25Δ risk reversal from (delta, iv) points.

    call_points: (delta in 0..1, iv). put_points: (delta in -1..0, iv).
    RR = IV(25Δ put) − IV(25Δ call). Positive = put bias (bearish lean).
    """
    iv_call, ex_c = interp_y(call_points, target_delta)
    iv_put, ex_p = interp_y(put_points, -target_delta)
    if iv_call is None or iv_put is None:
        return {"rr": None, "iv_call25": iv_call, "iv_put25": iv_put,
                "reliability": "low", "reason": "smile troppo rada"}
    rr = iv_put - iv_call
    n = min(len(call_points), len(put_points))
    reliability = "low" if (ex_c or ex_p or n < 3) else "ok"
    return {"rr": rr, "iv_call25": iv_call, "iv_put25": iv_put,
            "reliability": reliability}


def smile_points(quotes, spot: float, T: float, r: float):
    """Build (delta, iv) points for calls and puts from a chain (recompute IV+delta)."""
    calls: list[tuple[float, float]] = []
    puts: list[tuple[float, float]] = []
    for q in quotes:
        mid = _mid(q)
        if not mid:
            continue
        iv = opt.implied_vol(q.option_type, mid, spot, q.strike, T, r)
        if not iv:
            continue
        d = opt.greeks(q.option_type, spot, q.strike, T, r, iv).get("delta")
        if d is None:
            continue
        (calls if q.option_type == "call" else puts).append((d, iv))
    return calls, puts


def risk_reversal_from_quotes(quotes, spot: float, T: float, r: float) -> dict:
    calls, puts = smile_points(quotes, spot, T, r)
    return risk_reversal(calls, puts)


def _mid(q) -> float | None:
    if q.bid and q.ask and q.bid > 0 and q.ask > 0:
        return (q.bid + q.ask) / 2.0
    return q.last if (q.last and q.last > 0) else None


def rr_lean(rr: float | None) -> str:
    """Map a risk reversal to a directional LEAN label (not a probability)."""
    if rr is None:
        return "n/d"
    if rr > 0:
        return "bearish"   # put bias
    if rr < 0:
        return "bullish"   # call bias
    return "neutral"


# --- expected move on events (IV term structure) ---------------------
def expected_move_on_events(
    events: Sequence[dict],
    atm_iv_by_expiry: Sequence[dict],
    *,
    today: date,
) -> list[dict]:
    """±% the market prices into the expiry that SPANS each event.

    `atm_iv_by_expiry`: [{expiry 'YYYY-MM-DD', days_to_expiry, atm_iv}]. Magnitude
    only — never a direction.
    """
    import math

    expiries = sorted(
        [e for e in atm_iv_by_expiry if e.get("atm_iv") and e.get("days_to_expiry", 0) > 0],
        key=lambda e: e["days_to_expiry"],
    )
    out: list[dict] = []
    for ev in events:
        ed = _to_date(ev.get("event_time"))
        if ed is None or ed < today:
            continue
        dte_event = (ed - today).days
        spanning = next((e for e in expiries if e["days_to_expiry"] >= dte_event), None)
        if not spanning:
            continue
        T = spanning["days_to_expiry"] / 365.0
        move = spanning["atm_iv"] * math.sqrt(T)
        out.append({
            "event": ev.get("title"), "event_date": ed.isoformat(),
            "expiry": spanning["expiry"], "expected_move_pct": move * 100.0,
        })
    return out


# --- historical event behaviour --------------------------------------
def event_behaviour(
    dates: Sequence[str],
    closes_by_date: dict[str, float],
    event_dates: Sequence[date],
    *,
    follow_days: int = 3,
    min_sample: int = 20,
) -> dict:
    """For past events: median |day move| and how often the day's move CONTINUED
    vs REVERSED over the next `follow_days`. Frequency with n, never a forecast."""
    idx = {d: i for i, d in enumerate(dates)}
    abs_moves: list[float] = []
    continued = reversed_ = 0
    n = 0
    for ed in event_dates:
        key = ed.isoformat()
        i = idx.get(key)
        if i is None or i == 0:
            continue
        prev = closes_by_date[dates[i - 1]]
        cur = closes_by_date[dates[i]]
        if not prev:
            continue
        day_move = cur / prev - 1.0
        abs_moves.append(abs(day_move))
        j = i + follow_days
        if j < len(dates) and cur:
            fwd = closes_by_date[dates[j]] / cur - 1.0
            if day_move != 0 and fwd != 0:
                if (day_move > 0) == (fwd > 0):
                    continued += 1
                else:
                    reversed_ += 1
        n += 1

    decided = continued + reversed_
    status = "ok" if n >= min_sample else ("insufficient" if n > 0 else "none")
    return {
        "n": n,
        "median_abs_move_pct": (_median(abs_moves) * 100.0) if abs_moves else None,
        "pct_continued": (continued / decided) if decided else None,
        "pct_reversed": (reversed_ / decided) if decided else None,
        "follow_days": follow_days,
        "min_sample": min_sample,
        "status": status,
    }


# --- COT positioning percentile + state ------------------------------
def positioning_state(history: Sequence[float], latest: float | None,
                      *, hi: float = 0.9, lo: float = 0.1) -> dict:
    """Percentile of the latest net position over history + a contrarian state."""
    vals = [v for v in history if v is not None]
    if latest is None or not vals:
        return {"percentile": None, "state": "n/d", "n": len(vals)}
    le = sum(1 for v in vals if v <= latest)
    pct = le / len(vals)
    if pct >= hi:
        state = "crowded_long"     # very long -> reversal risk
    elif pct <= lo:
        state = "crowded_short"    # very short -> squeeze risk
    else:
        state = "neutral"
    return {"percentile": pct, "state": state, "n": len(vals)}


def cot_lean(state: str) -> str:
    """Contrarian lean ONLY at the extremes (else neutral)."""
    return {"crowded_long": "bearish", "crowded_short": "bullish"}.get(state, "neutral")


# --- helpers ---------------------------------------------------------
def _to_date(s) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def _median(xs: Sequence[float]) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2.0

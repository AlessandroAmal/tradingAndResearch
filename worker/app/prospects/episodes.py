"""Multi-year EPISODES — patterns too rare to be a statistic. PURE & TESTED.

Some things happen a handful of times in the data: >20% drawdowns, the Nth year
of a bull market, rate-hike cycles. Turning n<10 into a percentage is dishonest —
so this module returns the EPISODES ONE BY ONE (date, context, outcome) with the
count declared, and NEVER derives a probability below the threshold. It's meant to
be read, not averaged. Consumed by the Ricerca "Episodi" view.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date

MIN_FOR_PCT = 10   # below this, NO percentage is ever derived


def _to_date(s) -> date | None:
    try:
        return date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def _forward_return(closes: Sequence[float], t: int, horizon: int) -> float | None:
    if t + horizon < len(closes) and closes[t] > 0:
        return closes[t + horizon] / closes[t] - 1.0
    return None


def drawdown_episodes(dates: Sequence[str], closes: Sequence[float],
                      *, threshold: float = 0.20, forward: int = 252) -> dict:
    """Peak-to-trough drawdowns exceeding `threshold`; for each: start (peak),
    trough date/depth, and the forward return `forward` days after the trough."""
    episodes: list[dict] = []
    peak = closes[0] if closes else 0.0
    peak_i = 0
    in_dd = False
    trough = peak
    trough_i = 0
    for i in range(1, len(closes)):
        c = closes[i]
        if c > peak:
            if in_dd:                       # recovered above the old peak: close episode
                depth = trough / peak - 1.0
                episodes.append({
                    "peak_date": dates[peak_i], "trough_date": dates[trough_i],
                    "depth": depth, "recover_date": dates[i],
                    "forward_after_trough": _forward_return(closes, trough_i, forward),
                })
                in_dd = False
            peak, peak_i = c, i
            trough, trough_i = c, i
        else:
            if c < trough:
                trough, trough_i = c, i
            if not in_dd and (c / peak - 1.0) <= -threshold:
                in_dd = True
    if in_dd:                               # ongoing drawdown at series end
        episodes.append({
            "peak_date": dates[peak_i], "trough_date": dates[trough_i],
            "depth": trough / peak - 1.0, "recover_date": None,
            "forward_after_trough": _forward_return(closes, trough_i, forward),
            "ongoing": True,
        })
    return _wrap(episodes, f"Drawdown > {int(threshold * 100)}% (poi {forward}g)")


def bull_year_episodes(dates: Sequence[str], closes: Sequence[float], *, nth: int) -> dict:
    """Calendar years that are the Nth consecutive UP year of a bull run; for each,
    the next year's return. 'Up year' = Dec-close higher than the prior year's."""
    by_year: dict[int, float] = {}
    for d_iso, c in zip(dates, closes):
        d = _to_date(d_iso)
        if d is not None and c is not None:
            by_year[d.year] = float(c)      # ascending dates -> keeps year-end
    years = sorted(by_year)
    episodes: list[dict] = []
    run = 0
    for i in range(1, len(years)):
        y, prev = years[i], years[i - 1]
        up = by_year[y] > by_year[prev]
        run = run + 1 if up else 0
        if run == nth:
            nxt = years[i + 1] if i + 1 < len(years) else None
            fwd = (by_year[nxt] / by_year[y] - 1.0) if nxt else None
            episodes.append({"year": y, "run_length": run,
                             "next_year": nxt, "next_year_return": fwd})
    return _wrap(episodes, f"{nth}º anno consecutivo di rialzo (poi anno dopo)")


def _wrap(episodes: list[dict], label: str) -> dict:
    n = len(episodes)
    return {
        "label": label, "n": n, "episodes": episodes,
        "percentage_allowed": n >= MIN_FOR_PCT,
        "caveat": ("n troppo piccolo per una probabilità — episodi da leggere, non statistica."
                   if n < MIN_FOR_PCT else
                   f"n = {n}: ancora pochi casi, leggi gli episodi, non una singola percentuale."),
    }

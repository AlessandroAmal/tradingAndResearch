"""Expectancy & survival — the long-run math of the user's OWN trading. PURE & TESTED.

Everything here is MEASURED from the user's closed trades, never predicted. Every
statistic carries its sample size and a confidence interval; below a threshold the
numbers are explicitly "insufficient — noise". Risk-of-ruin and Kelly use the
MEASURED win rate / R:R, and the uncertainty-adjusted Kelly deliberately uses the
LOWER confidence bound (what's proven, not what's hoped). No directional numbers,
no "you're ready" — just the arithmetic and the thresholds.

Mirrored client-side in `lib/expectancy.js`.
"""
from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence

MIN_SAMPLE = 20


# --- per-trade R -----------------------------------------------------
def trade_r(entry, stop, realized_pnl, size, multiplier) -> float | None:
    """R multiple of a closed trade: realised P&L / the risk taken (entry→stop)."""
    try:
        entry = float(entry); size = float(size); multiplier = float(multiplier)
        if stop is None or realized_pnl is None:
            return None
        risk = abs(entry - float(stop)) * size * multiplier
        if risk <= 0:
            return None
        return float(realized_pnl) / risk
    except (TypeError, ValueError):
        return None


# --- confidence intervals -------------------------------------------
def wilson_ci(wins: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """Wilson score interval for a binomial win rate. None if n == 0."""
    if n <= 0:
        return None
    p = wins / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def bootstrap_ci(values: Sequence[float], *, n_boot: int = 2000, alpha: float = 0.05,
                 seed: int = 12345) -> tuple[float, float] | None:
    """Percentile bootstrap CI for the MEAN. Seeded for reproducibility."""
    vals = [float(v) for v in values if v is not None]
    n = len(vals)
    if n < 2:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(n_boot):
        s = 0.0
        for _ in range(n):
            s += vals[rng.randrange(n)]
        means.append(s / n)
    means.sort()
    lo = means[int((alpha / 2) * n_boot)]
    hi = means[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return (lo, hi)


# --- expectancy ------------------------------------------------------
def expectancy_stats(trades: Sequence[Mapping], *, min_sample: int = MIN_SAMPLE) -> dict:
    """From closed trades [{r, pnl}] → the honest long-run stats + intervals.

    `r` may be None (no stop) — such trades count for P&L but not for R stats.
    """
    pnls = [float(t["pnl"]) for t in trades if t.get("pnl") is not None]
    rs = [float(t["r"]) for t in trades if t.get("r") is not None]
    n = len(pnls)
    if n == 0:
        return {"n": 0, "sufficient": False, "min_sample": min_sample,
                "note": "Nessun trade chiuso: niente da misurare."}

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    win_rate = len(wins) / n
    win_r = [r for r in rs if r > 0]
    loss_r = [-r for r in rs if r < 0]        # positive magnitudes
    profit_factor = (sum(wins) / abs(sum(losses))) if losses else None

    # max consecutive losing streak (by P&L order as given, newest handling is the
    # caller's job; we take the sequence as-is / chronological).
    max_streak = streak = 0
    for p in pnls:
        streak = streak + 1 if p < 0 else 0
        max_streak = max(max_streak, streak)

    wr_ci = wilson_ci(len(wins), n)
    exp_r_ci = bootstrap_ci(rs) if len(rs) >= 2 else None
    exp_eur_ci = bootstrap_ci(pnls) if n >= 2 else None
    return {
        "n": n, "n_with_r": len(rs), "sufficient": n >= min_sample, "min_sample": min_sample,
        "win_rate": win_rate, "win_rate_ci": wr_ci,
        "avg_win_r": (sum(win_r) / len(win_r)) if win_r else None,
        "avg_loss_r": (sum(loss_r) / len(loss_r)) if loss_r else None,
        "expectancy_r": (sum(rs) / len(rs)) if rs else None, "expectancy_r_ci": exp_r_ci,
        "expectancy_eur": sum(pnls) / n, "expectancy_eur_ci": exp_eur_ci,
        "profit_factor": profit_factor, "max_consecutive_losses": max_streak,
        "note": (None if n >= min_sample else
                 f"Campione insufficiente (n={n} < {min_sample}): questi numeri sono RUMORE, continua a raccogliere."),
    }


# --- risk of ruin (Monte Carlo, fractional betting) ------------------
def risk_of_ruin(*, win_rate: float, rr: float, risk_frac: float,
                 drawdown: float = 0.5, target_multiple: float = 2.0,
                 n_runs: int = 10_000, max_trades: int = 5_000, seed: int = 7) -> float | None:
    """P(capital falls to (1−drawdown)×start BEFORE reaching target_multiple×start),
    betting `risk_frac` of CURRENT capital each trade (compounding). Measured inputs."""
    if not (0 < win_rate < 1) or rr <= 0 or not (0 < risk_frac < 1):
        return None
    rng = random.Random(seed)
    ruin_level = 1.0 - drawdown
    ruined = 0
    for _ in range(n_runs):
        cap = 1.0
        for _ in range(max_trades):
            if rng.random() < win_rate:
                cap *= 1.0 + risk_frac * rr
            else:
                cap *= 1.0 - risk_frac
            if cap <= ruin_level:
                ruined += 1
                break
            if cap >= target_multiple:
                break
    return ruined / n_runs


def ruin_curve(*, win_rate: float, rr: float, current_frac: float,
               fracs: Sequence[float] = (0.005, 0.01, 0.015, 0.02, 0.03, 0.05),
               **kw) -> list[dict]:
    """Risk of ruin across risk-per-trade fractions, flagging the user's current one."""
    out = []
    for fr in fracs:
        out.append({"risk_frac": fr,
                    "ruin": risk_of_ruin(win_rate=win_rate, rr=rr, risk_frac=fr, **kw),
                    "current": abs(fr - current_frac) < 1e-9})
    return out


# --- fractional Kelly, uncertainty-adjusted --------------------------
def kelly_fraction(win_rate: float, rr: float) -> float:
    """Kelly fraction of capital for a win/loss payoff of `rr`: W − (1−W)/R."""
    if rr <= 0:
        return 0.0
    return win_rate - (1.0 - win_rate) / rr


def kelly_adjusted(stats: Mapping) -> dict:
    """Kelly on the MEASURED edge, but using the LOWER win-rate bound (proven, not
    hoped). Returns full/half/quarter and whether the edge is demonstrated."""
    n = stats.get("n", 0)
    wr = stats.get("win_rate")
    avg_win = stats.get("avg_win_r")
    avg_loss = stats.get("avg_loss_r")
    ci = stats.get("win_rate_ci")
    if not wr or not avg_win or not avg_loss or avg_loss <= 0 or not ci:
        return {"proven": False, "n": n,
                "note": f"Edge non misurabile ancora (n={n}). Size suggerita: minima / di apprendimento."}
    rr = avg_win / avg_loss
    wr_lower = ci[0]
    kelly_mean = kelly_fraction(wr, rr)
    kelly_lb = kelly_fraction(wr_lower, rr)          # uncertainty-penalised
    proven = kelly_lb > 0 and n >= stats.get("min_sample", MIN_SAMPLE)
    return {
        "proven": proven, "n": n, "rr": rr,
        "kelly_mean": kelly_mean, "kelly_lower": kelly_lb,
        "half_kelly": max(kelly_lb, 0) / 2, "quarter_kelly": max(kelly_lb, 0) / 4,
        "note": ("Quanto puoi permetterti dato ciò che è DIMOSTRATO, non ciò che speri."
                 if proven else
                 f"Il tuo edge non è ancora dimostrato dai dati (n={n}). Size suggerita: minima / di apprendimento."),
    }


# --- process scorecard (from gate warnings recorded at open) ---------
def process_scorecard(trades: Sequence[Mapping], *, min_sample: int = MIN_SAMPLE) -> dict:
    """Split closed trades into 'within rules' vs 'forced past warnings' (from the
    gate warnings stored at open) and measure each. Discipline, made measurable."""
    clean = [t for t in trades if not t.get("forced")]
    forced = [t for t in trades if t.get("forced")]
    total = len(trades)
    return {
        "n": total,
        "pct_clean": (len(clean) / total) if total else None,
        "pct_forced": (len(forced) / total) if total else None,
        "clean": expectancy_stats(clean, min_sample=min_sample),
        "forced": expectancy_stats(forced, min_sample=min_sample),
        "note": "La disciplina è misurabile: expectancy dei trade dentro le regole vs forzati (con n di entrambi).",
    }

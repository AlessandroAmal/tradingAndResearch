"""Indicator calibration — does each factor actually predict? PURE & TESTED.

For every factor the cockpit computes, measure its predictive value on long
history, at several horizons, WITHOUT look-ahead (the signal at t uses only data
up to t; the return is t→t+h). We report:
  * Information Coefficient — Spearman rank corr(signal_t, forward_return) — with
    a bootstrap CI and sub-period stability;
  * directional hit rate (sign match) with n;
  * a deflation reminder: we run factors × horizons × instruments tests, so
    "significant on N tests" is not the same as "true".

The honest expectation is that MOST factors have IC ≈ 0. That is the informative
result, not a failure. Nothing here is a forecast or an order.

`causal_technical_signals` reconstructs the technical factors from price history
alone (RSI, streak, trend-vs-MA, distance-from-MA) so they are testable without a
look-ahead. Macro signals are built by the runner from stored FRED history.
Mirrored/consumed by the "Calibrazione indicatori" view. Tested in
`worker/tests/test_calibration.py`.
"""
from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence

HORIZONS = (1, 3, 5, 10, 15, 21)
MIN_SAMPLE = 30


# --- rank correlation (Spearman) -------------------------------------
def _rank(xs: Sequence[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0            # average rank for ties
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _pearson(a: Sequence[float], b: Sequence[float]) -> float | None:
    n = len(a)
    if n < 2:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((x - mb) ** 2 for x in b))
    if da == 0 or db == 0:
        return None
    return num / (da * db)


def spearman(x: Sequence[float], y: Sequence[float]) -> float | None:
    if len(x) != len(y) or len(x) < 2:
        return None
    return _pearson(_rank(x), _rank(y))


# --- forward returns + IC/hit ----------------------------------------
def forward_returns(closes: Sequence[float], horizon: int) -> list[float | None]:
    """r_{t→t+h} aligned to index t (None where t+h is out of range)."""
    n = len(closes)
    out: list[float | None] = []
    for t in range(n):
        if t + horizon < n and closes[t] > 0:
            out.append(closes[t + horizon] / closes[t] - 1.0)
        else:
            out.append(None)
    return out


def _aligned(signal: Sequence[float | None], fwd: Sequence[float | None]):
    xs, ys = [], []
    for s, r in zip(signal, fwd):
        if s is not None and r is not None:
            xs.append(float(s)); ys.append(float(r))
    return xs, ys


def bootstrap_ic_ci(xs: Sequence[float], ys: Sequence[float], *, n_boot: int = 1000,
                    alpha: float = 0.05, seed: int = 20240607) -> tuple[float, float] | None:
    n = len(xs)
    if n < 8:
        return None
    rng = random.Random(seed)
    ics = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        ic = spearman([xs[i] for i in idx], [ys[i] for i in idx])
        if ic is not None:
            ics.append(ic)
    if len(ics) < 2:
        return None
    ics.sort()
    lo = ics[int((alpha / 2) * len(ics))]
    hi = ics[min(len(ics) - 1, int((1 - alpha / 2) * len(ics)))]
    return (lo, hi)


def calibrate_factor(signal: Sequence[float | None], closes: Sequence[float],
                     horizon: int, *, min_sample: int = MIN_SAMPLE,
                     subperiods: int = 3) -> dict:
    """IC + hit rate + n + sub-period stability + bootstrap significance for ONE
    factor at ONE horizon. `significant` = bootstrap CI excludes 0 AND n≥min."""
    fwd = forward_returns(closes, horizon)
    xs, ys = _aligned(signal, fwd)
    n = len(xs)
    if n < 2:
        return {"horizon": horizon, "n": n, "ic": None, "hit_rate": None,
                "sufficient": False, "significant": False}
    ic = spearman(xs, ys)
    # directional hit rate on the SIGN of the signal (0 signals ignored).
    hits = tot = 0
    for s, r in zip(xs, ys):
        if s == 0:
            continue
        tot += 1
        if (s > 0 and r > 0) or (s < 0 and r < 0):
            hits += 1
    hit_rate = (hits / tot) if tot else None
    ci = bootstrap_ic_ci(xs, ys)
    sub = []
    if subperiods > 1 and n >= subperiods * 5:
        step = n // subperiods
        for k in range(subperiods):
            a, b = k * step, (n if k == subperiods - 1 else (k + 1) * step)
            sub.append(spearman(xs[a:b], ys[a:b]))
    significant = bool(ci and (ci[0] > 0 or ci[1] < 0) and n >= min_sample)
    return {
        "horizon": horizon, "n": n, "n_directional": tot,
        "ic": ic, "ic_ci": ci, "hit_rate": hit_rate, "subperiod_ic": sub,
        "sufficient": n >= min_sample, "significant": significant,
    }


def calibrate_signals(signals: Mapping[str, Sequence[float | None]],
                      closes: Sequence[float], *, horizons: Sequence[int] = HORIZONS,
                      min_sample: int = MIN_SAMPLE) -> dict:
    """Calibrate every factor at every horizon. Returns {factor: {horizon: stats}}
    plus a deflation test-count (factors × horizons)."""
    out: dict[str, dict] = {}
    for name, sig in signals.items():
        out[name] = {str(h): calibrate_factor(sig, closes, h, min_sample=min_sample)
                     for h in horizons}
    return {"factors": out, "test_count": len(signals) * len(horizons),
            "horizons": list(horizons)}


# --- causal technical signals (from price history only) --------------
def _rsi_series(closes: Sequence[float], period: int, overbought: float,
                oversold: float) -> list[float | None]:
    """Causal RSI classification: overbought → −1 (mean-reversion bearish),
    oversold → +1, else 0. RSI at t uses only closes ≤ t."""
    out: list[float | None] = [None] * len(closes)
    if len(closes) <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        ch = closes[i] - closes[i - 1]
        gains += max(ch, 0); losses += max(-ch, 0)
    avg_g, avg_l = gains / period, losses / period
    for t in range(period, len(closes)):
        if t > period:
            ch = closes[t] - closes[t - 1]
            avg_g = (avg_g * (period - 1) + max(ch, 0)) / period
            avg_l = (avg_l * (period - 1) + max(-ch, 0)) / period
        rsi = 100.0 if avg_l == 0 else 100.0 - 100.0 / (1.0 + avg_g / avg_l)
        out[t] = -1.0 if rsi >= overbought else 1.0 if rsi <= oversold else 0.0
    return out


def _streak_series(closes: Sequence[float]) -> list[float | None]:
    """Signed momentum: +len up-run / −len down-run at t (causal)."""
    out: list[float | None] = [None] * len(closes)
    run = 0
    for t in range(1, len(closes)):
        if closes[t] > closes[t - 1]:
            run = run + 1 if run > 0 else 1
        elif closes[t] < closes[t - 1]:
            run = run - 1 if run < 0 else -1
        else:
            run = 0
        out[t] = float(run)
    return out


def _sma(closes: Sequence[float], t: int, period: int) -> float | None:
    if t + 1 < period:
        return None
    return sum(closes[t - period + 1:t + 1]) / period


def _trend_series(closes: Sequence[float]) -> list[float | None]:
    """+1 above a rising MA200, −1 below a falling MA50, else 0 (causal)."""
    out: list[float | None] = [None] * len(closes)
    for t in range(len(closes)):
        ma200, ma50 = _sma(closes, t, 200), _sma(closes, t, 50)
        if ma200 is None:
            continue
        rising200 = ma200 is not None and _sma(closes, t - 1, 200) is not None and ma200 > _sma(closes, t - 1, 200)
        falling50 = ma50 is not None and _sma(closes, t - 1, 50) is not None and ma50 < _sma(closes, t - 1, 50)
        if closes[t] > ma200 and rising200:
            out[t] = 1.0
        elif ma50 is not None and closes[t] < ma50 and falling50:
            out[t] = -1.0
        else:
            out[t] = 0.0
    return out


def _ma_dist_series(closes: Sequence[float], period: int = 200) -> list[float | None]:
    """Continuous distance from the MA (close/MA − 1): tests if extension predicts."""
    out: list[float | None] = [None] * len(closes)
    for t in range(len(closes)):
        ma = _sma(closes, t, period)
        if ma and ma > 0:
            out[t] = closes[t] / ma - 1.0
    return out


def causal_technical_signals(closes: Sequence[float], *, rsi_period: int = 14,
                             overbought: float = 70, oversold: float = 30) -> dict:
    """The technical factors, reconstructed causally from closes."""
    return {
        "rsi": _rsi_series(closes, rsi_period, overbought, oversold),
        "streak": _streak_series(closes),
        "trend_ma": _trend_series(closes),
        "ma200_dist": _ma_dist_series(closes, 200),
    }


# --- evidence-based weights (Part B) ---------------------------------
def derive_weights(factor_results: Mapping[str, Mapping], *, horizon: int) -> dict:
    """Turn one instrument's calibration into lean weights for `horizon`.

    Weight ∝ IC ONLY for factors that are significant AND aligned (IC>0: the
    signal already encodes the expected bullish direction, so a genuine edge is
    POSITIVE IC). Significant-but-negative = CONTRARY → weight 0 and flagged (we do
    NOT auto-invert: that would be data-mining). Non-significant → weight 0.
    """
    out: dict[str, dict] = {}
    for name, by_h in factor_results.items():
        st = by_h.get(str(horizon)) or {}
        ic = st.get("ic")
        sig = st.get("significant")
        if not sig or ic is None:
            out[name] = {"weight": 0.0, "ic": ic, "significant": bool(sig), "contrary": False,
                         "reason": "nessun valore predittivo misurato a questo orizzonte"}
        elif ic < 0:
            out[name] = {"weight": 0.0, "ic": ic, "significant": True, "contrary": True,
                         "reason": "risultato CONTRARIO: azzerato, non invertito (anti data-mining)"}
        else:
            out[name] = {"weight": round(abs(ic), 4), "ic": ic, "significant": True, "contrary": False,
                         "reason": "significativo e allineato: peso ∝ IC out-of-sample"}
    return out

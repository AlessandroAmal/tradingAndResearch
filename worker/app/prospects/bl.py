"""Breeden-Litzenberger — the risk-neutral density implied by an option chain.

The market's option prices imply a full distribution of the underlying at expiry,
not just an ATM ±1σ. Breeden-Litzenberger (1978):

    f(K) = e^{rT} · ∂²C/∂K²          (risk-neutral density at strike K)
    P(S_T ≤ K) = 1 + e^{rT} · ∂C/∂K  (risk-neutral CDF)

We build a smooth call-price curve C(K) across strikes (fitting the IV smile and
re-pricing with Black-Scholes so the curve is arbitrage-consistent and denoised),
then take numerical derivatives. Tails beyond the quoted strikes are extended with
the edge lognormal so the density integrates ~1.

These are RISK-NEUTRAL odds (what the market prices), NOT real-world probabilities
— labelled as such everywhere. Pure (BS only); tested in test_prospects_bl.py.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

from .. import options as opt


def _mid(bid, ask, last) -> float | None:
    if bid and ask and bid > 0 and ask > 0:
        return (bid + ask) / 2.0
    return last if (last and last > 0) else None


def call_iv_curve(quotes: Sequence, spot: float, T: float, r: float, *,
                  moneyness_lo: float = 0.6, moneyness_hi: float = 1.6,
                  iv_lo: float = 0.02, iv_hi: float = 2.0,
                  require_bid: bool = True) -> list[tuple[float, float]]:
    """(strike, IV) points from the chain, LIQUIDITY-FILTERED.

    Deep-OTM strikes on free feeds are near-zero, illiquid, and their implied vol
    is garbage — left in, they distort the smile and skew the BL density's median
    (a real bug seen on long-dated GLD). So we keep only strikes within a moneyness
    band, with a genuine two-sided market (bid>0) and a plausible IV."""
    lo, hi = spot * moneyness_lo, spot * moneyness_hi
    by_strike: dict[float, list[float]] = {}
    for q in quotes:
        if q.strike < lo or q.strike > hi:
            continue
        if require_bid and not (q.bid and q.bid > 0):     # no real market -> skip
            continue
        m = _mid(q.bid, q.ask, q.last)
        if not m:
            continue
        iv = opt.implied_vol(q.option_type, m, spot, q.strike, T, r)
        if iv and iv_lo <= iv <= iv_hi:
            by_strike.setdefault(q.strike, []).append(iv)
    pts = [(k, sum(v) / len(v)) for k, v in sorted(by_strike.items())]
    # fallback: if the bid filter emptied it (thin feed), retry without it.
    if len(pts) < 5 and require_bid:
        return call_iv_curve(quotes, spot, T, r, moneyness_lo=moneyness_lo,
                             moneyness_hi=moneyness_hi, iv_lo=iv_lo, iv_hi=iv_hi, require_bid=False)
    return pts


def _fit_smile(points: list[tuple[float, float]], spot: float):
    """Fit IV as a QUADRATIC in log-moneyness x=ln(K/spot): iv ≈ a + b·x + c·x².

    A piecewise-linear smile, re-priced with BS, gives a kinky call curve whose
    numerical 2nd derivative spikes — producing a degenerate BL density (real bug
    on long-dated GLD: a 6% median band at +32%). A smooth parametric fit gives a
    stable, differentiable curve. Returns a callable iv(K); flat/linear fallback
    for <3 points. Clamped to the observed IV range so the wings can't explode."""
    pts = [(k, v) for k, v in points if k > 0 and v and v > 0]
    if len(pts) < 3:
        if not pts:
            return lambda k: float("nan")
        avg = sum(v for _, v in pts) / len(pts)
        return lambda k: avg
    import math as _m
    xs = [_m.log(k / spot) for k, _ in pts]
    ys = [v for _, v in pts]
    # least squares for [1, x, x²] via 3x3 normal equations (stdlib only)
    n = len(xs)
    sx = sum(xs); sx2 = sum(x * x for x in xs); sx3 = sum(x ** 3 for x in xs); sx4 = sum(x ** 4 for x in xs)
    sy = sum(ys); sxy = sum(x * y for x, y in zip(xs, ys)); sx2y = sum(x * x * y for x, y in zip(xs, ys))
    A = [[n, sx, sx2], [sx, sx2, sx3], [sx2, sx3, sx4]]
    b = [sy, sxy, sx2y]
    coef = _solve3(A, b)
    if coef is None:
        avg = sy / n
        return lambda k: avg
    a0, a1, a2 = coef
    iv_lo, iv_hi = min(ys), max(ys)

    def iv(k: float) -> float:
        x = _m.log(max(k, 1e-9) / spot)
        return min(max(a0 + a1 * x + a2 * x * x, iv_lo * 0.5), iv_hi * 1.5)

    return iv


def _solve3(A, b):
    """Solve a 3x3 linear system by Gaussian elimination; None if singular."""
    m = [row[:] + [b[i]] for i, row in enumerate(A)]
    for i in range(3):
        piv = max(range(i, 3), key=lambda r: abs(m[r][i]))
        if abs(m[piv][i]) < 1e-12:
            return None
        m[i], m[piv] = m[piv], m[i]
        for r in range(3):
            if r != i:
                f = m[r][i] / m[i][i]
                for c in range(i, 4):
                    m[r][c] -= f * m[i][c]
    return [m[i][3] / m[i][i] for i in range(3)]


def risk_neutral_density(quotes: Sequence, spot: float, T: float, r: float,
                         *, grid_points: int = 201, span: float = 3.0) -> dict:
    """Return the risk-neutral density + CDF on a strike grid via Breeden-
    Litzenberger over the SMOOTHED (BS-repriced) call curve.

    `span` = how many ATM sigmas each side to cover the grid. Returns
    {strikes, pdf, cdf, spot, quality:{n_strikes, coverage, reliable}}."""
    pts = call_iv_curve(quotes, spot, T, r)
    n_strikes = len(pts)
    smile = _fit_smile(pts, spot) if pts else (lambda k: float("nan"))
    atm_iv = smile(spot) if pts else float("nan")
    if n_strikes < 3 or not (atm_iv == atm_iv) or T <= 0 or spot <= 0:
        return {"strikes": [], "pdf": [], "cdf": [], "spot": spot,
                "quality": {"n_strikes": n_strikes, "coverage": 0.0, "reliable": False,
                            "note": "catena troppo sottile per una densità affidabile"}}

    sd = atm_iv * math.sqrt(T)
    lo = max(spot * math.exp(-span * sd), 1e-9)
    hi = spot * math.exp(span * sd)
    step = (hi - lo) / (grid_points - 1)

    def call(k: float) -> float:
        return opt.bs_price("call", spot, k, T, r, max(smile(k), 1e-6))

    strikes = [lo + i * step for i in range(grid_points)]
    disc = math.exp(r * T)
    pdf: list[float] = []
    for k in strikes:
        c_m, c_0, c_p = call(k - step), call(k), call(k + step)
        d2 = (c_p - 2.0 * c_0 + c_m) / (step * step)
        pdf.append(max(disc * d2, 0.0))          # density is non-negative
    # normalise (handles truncated tails) and integrate to a CDF (trapezoid).
    area = sum(pdf) * step
    if area > 0:
        pdf = [p / area for p in pdf]
    cdf: list[float] = []
    acc = 0.0
    for i, p in enumerate(pdf):
        if i > 0:
            acc += 0.5 * (pdf[i] + pdf[i - 1]) * step
        cdf.append(min(acc, 1.0))

    quoted_lo, quoted_hi = pts[0][0], pts[-1][0]
    coverage = max(0.0, min(1.0, (min(quoted_hi, hi) - max(quoted_lo, lo)) / (hi - lo)))
    reliable = n_strikes >= 6 and coverage >= 0.5
    return {
        "strikes": strikes, "pdf": pdf, "cdf": cdf, "spot": spot,
        "atm_iv": atm_iv,
        "quality": {"n_strikes": n_strikes, "coverage": round(coverage, 3),
                    "reliable": reliable,
                    "note": None if reliable else "affidabilità bassa (pochi strike o copertura ridotta)"},
    }


# --- queries on the density ------------------------------------------
def _interp_cdf(dens: dict, level: float) -> float | None:
    strikes, cdf = dens.get("strikes"), dens.get("cdf")
    if not strikes or not cdf:
        return None
    if level <= strikes[0]:
        return cdf[0]
    if level >= strikes[-1]:
        return cdf[-1]
    for i in range(1, len(strikes)):
        if strikes[i - 1] <= level <= strikes[i]:
            w = (level - strikes[i - 1]) / (strikes[i] - strikes[i - 1])
            return cdf[i - 1] + w * (cdf[i] - cdf[i - 1])
    return cdf[-1]


def prob_below(dens: dict, level: float) -> float | None:
    return _interp_cdf(dens, level)


def prob_above(dens: dict, level: float) -> float | None:
    c = _interp_cdf(dens, level)
    return None if c is None else max(0.0, 1.0 - c)


def percentile(dens: dict, p: float) -> float | None:
    """Inverse CDF: the price level at cumulative probability p (0..1)."""
    strikes, cdf = dens.get("strikes"), dens.get("cdf")
    if not strikes or not cdf:
        return None
    if p <= cdf[0]:
        return strikes[0]
    if p >= cdf[-1]:
        return strikes[-1]
    for i in range(1, len(cdf)):
        if cdf[i - 1] <= p <= cdf[i]:
            w = (p - cdf[i - 1]) / (cdf[i] - cdf[i - 1]) if cdf[i] > cdf[i - 1] else 0.0
            return strikes[i - 1] + w * (strikes[i] - strikes[i - 1])
    return strikes[-1]


def prob_above_return(dens: dict, ret: float) -> float | None:
    """P(return ≥ ret) where the return is measured vs the PROXY spot."""
    ps = dens.get("spot")
    if not ps:
        return None
    return prob_above(dens, ps * (1.0 + ret))


def return_summary(dens: dict) -> dict:
    """Distribution expressed as RETURNS vs the proxy spot (moneyness − 1).

    Proxy-agnostic: these returns can be applied to ANY instrument's spot to get
    levels/percentiles. This is the ONLY correct way to combine a proxy chain
    (e.g. GLD ~400) with the instrument's own spot (e.g. GC=F ~4437)."""
    if not dens.get("strikes"):
        return {"available": False, "quality": dens.get("quality")}
    ps = dens.get("spot")

    def ret(p: float):
        v = percentile(dens, p)
        return None if (v is None or not ps) else v / ps - 1.0

    return {
        "available": True,
        "median_ret": ret(0.5),
        "p16_ret": ret(0.16), "p84_ret": ret(0.84),
        "p2_5_ret": ret(0.025), "p97_5_ret": ret(0.975),
        "proxy_spot": ps,
        "quality": dens.get("quality"),
        "note": "Distribuzione risk-neutral in RENDIMENTI (vs spot proxy); applicata allo spot dello strumento.",
    }


def summary(dens: dict, *, level: float | None = None) -> dict:
    """Median + 68/95 intervals + optional prob above/below a level."""
    if not dens.get("strikes"):
        return {"available": False, "quality": dens.get("quality")}
    out = {
        "available": True,
        "median": percentile(dens, 0.5),
        "p16": percentile(dens, 0.16), "p84": percentile(dens, 0.84),   # ~68%
        "p2_5": percentile(dens, 0.025), "p97_5": percentile(dens, 0.975),  # ~95%
        "quality": dens.get("quality"),
        "note": "Distribuzione risk-neutral implicita nelle opzioni (odds del mercato), NON probabilità del mondo reale.",
    }
    if level is not None:
        out["prob_above"] = prob_above(dens, level)
        out["prob_below"] = prob_below(dens, level)
        out["level"] = level
    return out

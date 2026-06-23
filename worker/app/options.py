"""Options quant layer (M5) — pure, testable, NO I/O.

The brief's most quant-heavy piece, so it lives here with serious unit tests
(`worker/tests/test_options.py`). READ-ONLY: this ANALYSES and PROPOSES
structures — it never sends an order.

Conventions:
  - Black-Scholes (European) — the pragmatic approximation for this analysis
    desk (real US equity options are American; BS is close enough here).
  - S spot, K strike, T years-to-expiry, r risk-free (decimal, e.g. 0.04),
    sigma annualised vol (decimal).
  - We RECALCULATE IV from the market mid (Yahoo's IV is unreliable), then
    derive Greeks from that IV.
  - Greek units: delta unitless; gamma per $1; vega per 1.00 vol (×0.01 for
    per-1%); theta per YEAR (÷365 for per-day); rho per 1.00 rate.
  - "Probability of profit" is the RISK-NEUTRAL probability implied by option
    prices — an implied probability, NOT a forecast. Label it as such.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

SQRT2 = math.sqrt(2.0)


# --- normal distribution (stdlib only) --------------------------------
def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / SQRT2))


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _d1_d2(S: float, K: float, T: float, r: float, sigma: float) -> tuple[float, float]:
    vt = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / vt
    return d1, d1 - vt


# --- Black-Scholes price ---------------------------------------------
def bs_price(option_type: str, S: float, K: float, T: float, r: float, sigma: float) -> float:
    if T <= 0 or sigma <= 0:
        # Degenerate -> intrinsic value.
        return max(S - K, 0.0) if option_type == "call" else max(K - S, 0.0)
    d1, d2 = _d1_d2(S, K, T, r, sigma)
    disc = math.exp(-r * T)
    if option_type == "call":
        return S * norm_cdf(d1) - K * disc * norm_cdf(d2)
    return K * disc * norm_cdf(-d2) - S * norm_cdf(-d1)


# --- implied volatility solver (bisection; robust) -------------------
def implied_vol(
    option_type: str,
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    *,
    lo: float = 1e-4,
    hi: float = 5.0,
    tol: float = 1e-6,
    max_iter: int = 100,
) -> float | None:
    """Solve sigma so BS price == market_price. None if no valid solution."""
    if market_price is None or market_price <= 0 or T <= 0 or S <= 0 or K <= 0:
        return None
    disc = math.exp(-r * T)
    intrinsic = max(S - K * disc, 0.0) if option_type == "call" else max(K * disc - S, 0.0)
    upper = S if option_type == "call" else K * disc
    # Price must sit within no-arbitrage bounds, else IV is undefined.
    if market_price < intrinsic - tol or market_price > upper + tol:
        return None

    def f(sig: float) -> float:
        return bs_price(option_type, S, K, T, r, sig) - market_price

    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        return None  # not bracketed
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if abs(fm) < tol:
            return mid
        if flo * fm < 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return 0.5 * (lo + hi)


# --- Greeks -----------------------------------------------------------
def greeks(option_type: str, S: float, K: float, T: float, r: float, sigma: float) -> dict[str, float]:
    if T <= 0 or sigma <= 0:
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}
    d1, d2 = _d1_d2(S, K, T, r, sigma)
    pdf = norm_pdf(d1)
    disc = math.exp(-r * T)
    sqrtT = math.sqrt(T)
    gamma = pdf / (S * sigma * sqrtT)
    vega = S * pdf * sqrtT  # per 1.00 vol
    if option_type == "call":
        delta = norm_cdf(d1)
        theta = -(S * pdf * sigma) / (2 * sqrtT) - r * K * disc * norm_cdf(d2)
        rho = K * T * disc * norm_cdf(d2)
    else:
        delta = norm_cdf(d1) - 1.0
        theta = -(S * pdf * sigma) / (2 * sqrtT) + r * K * disc * norm_cdf(-d2)
        rho = -K * T * disc * norm_cdf(-d2)
    return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega, "rho": rho}


# --- risk-neutral (implied) probabilities -----------------------------
def prob_above(S: float, X: float, T: float, r: float, sigma: float) -> float | None:
    """Risk-neutral P(S_T > X). Implied probability, NOT a forecast."""
    if T <= 0 or sigma <= 0 or S <= 0 or X <= 0:
        return None
    _, d2 = _d1_d2(S, X, T, r, sigma)
    return norm_cdf(d2)


def prob_below(S: float, X: float, T: float, r: float, sigma: float) -> float | None:
    p = prob_above(S, X, T, r, sigma)
    return None if p is None else 1.0 - p


# --- structures -------------------------------------------------------
@dataclass(frozen=True)
class Leg:
    kind: str            # 'call' | 'put' | 'stock'
    side: str            # 'long' | 'short'
    premium: float       # option premium, or entry price for a stock leg
    strike: float | None = None
    qty: float = 1.0


def leg_pnl(leg: Leg, S: float) -> float:
    sgn = 1.0 if leg.side == "long" else -1.0
    if leg.kind == "stock":
        intrinsic = S - leg.premium
    elif leg.kind == "call":
        intrinsic = max(S - leg.strike, 0.0) - leg.premium
    else:  # put
        intrinsic = max(leg.strike - S, 0.0) - leg.premium
    return sgn * leg.qty * intrinsic


def structure_pnl(legs: list[Leg], S: float) -> float:
    return sum(leg_pnl(leg, S) for leg in legs)


def payoff_curve(legs: list[Leg], lo: float, hi: float, steps: int = 80) -> list[dict[str, float]]:
    if steps < 2 or hi <= lo:
        return []
    step = (hi - lo) / (steps - 1)
    return [{"price": lo + i * step, "pnl": structure_pnl(legs, lo + i * step)} for i in range(steps)]


@dataclass(frozen=True)
class StructureMetrics:
    legs: list[Leg]
    net_cost: float          # >0 debit paid, <0 credit received
    max_loss: float | None   # positive magnitude; None = unlimited
    max_gain: float | None
    breakeven: float | None
    profit_side: str         # 'above' | 'below' (relative to breakeven)
    risk_reward: float | None = field(default=None)


def _rr(max_gain: float | None, max_loss: float | None) -> float | None:
    if max_gain is None or max_loss is None or max_loss == 0:
        return None
    return max_gain / max_loss


def single_leg(option_type: str, side: str, strike: float, premium: float) -> StructureMetrics:
    leg = Leg(kind=option_type, side=side, premium=premium, strike=strike)
    if option_type == "call":
        breakeven = strike + premium
        if side == "long":
            ml, mg, ps = premium, None, "above"
        else:
            ml, mg, ps = None, premium, "below"
    else:  # put
        breakeven = strike - premium
        if side == "long":
            ml, mg, ps = premium, max(strike - premium, 0.0), "below"
        else:
            ml, mg, ps = max(strike - premium, 0.0), premium, "above"
    net = premium if side == "long" else -premium
    return StructureMetrics([leg], net, ml, mg, breakeven, ps, _rr(mg, ml))


def vertical_spread(
    option_type: str,
    long_strike: float, long_premium: float,
    short_strike: float, short_premium: float,
) -> StructureMetrics:
    """Debit/credit vertical with two same-type legs."""
    legs = [
        Leg(kind=option_type, side="long", premium=long_premium, strike=long_strike),
        Leg(kind=option_type, side="short", premium=short_premium, strike=short_strike),
    ]
    width = abs(short_strike - long_strike)
    net = long_premium - short_premium  # >0 debit, <0 credit
    if net >= 0:  # debit: max loss = debit, max gain = width - debit
        max_loss, max_gain = net, width - net
    else:         # credit: max gain = credit, max loss = width - credit
        max_gain, max_loss = -net, width + net
    # Call vertical resolves at the LOWER strike, put vertical at the UPPER.
    if option_type == "call":
        breakeven = min(long_strike, short_strike) + abs(net)
        profit_side = "above" if net >= 0 else "below"  # debit=bull, credit=bear
    else:
        breakeven = max(long_strike, short_strike) - abs(net)
        profit_side = "below" if net >= 0 else "above"  # debit=bear, credit=bull
    return StructureMetrics(
        legs, net, abs(max_loss), abs(max_gain), breakeven, profit_side,
        _rr(abs(max_gain), abs(max_loss)),
    )


def protective_put(entry: float, put_strike: float, put_premium: float, qty: float = 1.0) -> StructureMetrics:
    """Long stock + long put. Floor = put_strike - entry - premium."""
    legs = [
        Leg(kind="stock", side="long", premium=entry, qty=qty),
        Leg(kind="put", side="long", premium=put_premium, strike=put_strike, qty=qty),
    ]
    floor_per_share = put_strike - entry - put_premium  # P&L floor (may be <0)
    max_loss = -floor_per_share * qty if floor_per_share < 0 else 0.0
    breakeven = entry + put_premium
    return StructureMetrics(legs, put_premium * qty, max_loss, None, breakeven, "above", None)


def collar(
    entry: float, put_strike: float, put_premium: float,
    call_strike: float, call_premium: float, qty: float = 1.0,
) -> StructureMetrics:
    """Long stock + long put + short call. Bounded both sides."""
    legs = [
        Leg(kind="stock", side="long", premium=entry, qty=qty),
        Leg(kind="put", side="long", premium=put_premium, strike=put_strike, qty=qty),
        Leg(kind="call", side="short", premium=call_premium, strike=call_strike, qty=qty),
    ]
    net_debit = put_premium - call_premium
    floor_per_share = put_strike - entry - net_debit         # worst case (S <= put)
    cap_per_share = call_strike - entry - net_debit          # best case (S >= call)
    max_loss = -floor_per_share * qty if floor_per_share < 0 else 0.0
    max_gain = cap_per_share * qty if cap_per_share > 0 else 0.0
    breakeven = entry + net_debit
    return StructureMetrics(legs, net_debit * qty, max_loss, max_gain, breakeven, "above", _rr(max_gain, max_loss))


def probability_of_profit(
    m: StructureMetrics, S: float, T: float, r: float, sigma: float
) -> float | None:
    """Risk-neutral (implied) probability the structure is profitable at expiry.

    Implied by option prices — NOT a forecast. Uses the structure's single
    breakeven and profit side.
    """
    if m.breakeven is None:
        return None
    if m.profit_side == "above":
        return prob_above(S, m.breakeven, T, r, sigma)
    return prob_below(S, m.breakeven, T, r, sigma)

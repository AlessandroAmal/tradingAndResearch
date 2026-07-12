"""Decision bench — the arithmetic of ONE specific bet. PURE & TESTED.

Organises numbers around a chosen (instrument, direction, horizon, entry, stop,
target, risk%). The ONLY probabilities are the option-IMPLIED ones (computed by
`implied`/`options`, passed in) — this module NEVER fabricates a directional
probability. It produces:
  * R:R and the COST-ADJUSTED break-even win rate (the win rate you need just to
    not lose money after spread/commissions);
  * a scenario ladder (±ATR, stop, target, gap-through-stop) in P&L;
  * a defined-risk option ILLUSTRATION (BS-priced long call/put) to compare with
    the direct stop-based bet.

Honest by construction: EV talk uses only the implied odds and states that beating
them needs a THESIS; costs are always included; nothing says buy/sell. Mirrored
client-side in `lib/bench.js`. Tested in `worker/tests/test_bench.py`.
"""
from __future__ import annotations

import math
from collections.abc import Sequence


# --- normal helpers (same math as the client BS engine) --------------
def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _sign(direction: str) -> float:
    return 1.0 if direction == "long" else -1.0


# --- cost model ------------------------------------------------------
def cost_amount(entry: float, size: float, multiplier: float,
                spread_bps: float, commission: float = 0.0) -> float:
    """Round-trip cost in currency: spread (bps of notional) + flat commission."""
    notional = abs(entry) * size * multiplier
    return notional * (spread_bps / 10_000.0) + commission


# --- bet arithmetic --------------------------------------------------
def r_multiple(entry: float, stop: float | None, target: float | None) -> float | None:
    if stop is None or target is None:
        return None
    risk = abs(entry - stop)
    if risk == 0:
        return None
    return abs(target - entry) / risk


def breakeven_winrate(risk_amount: float, reward_amount: float,
                      cost: float = 0.0) -> float | None:
    """Win rate needed for EV=0 AFTER costs: (risk+cost)/(risk+reward).

    EV = p·reward − (1−p)·risk − cost = 0  ⇒  p = (risk + cost)/(risk + reward)."""
    denom = risk_amount + reward_amount
    if denom <= 0:
        return None
    return (risk_amount + cost) / denom


def bet_math(*, entry: float, stop: float | None, target: float | None,
             size: float, multiplier: float, spread_bps: float,
             commission: float = 0.0) -> dict:
    """R:R + cost-adjusted break-even win rate for the direct (stop-based) bet."""
    risk_amt = abs(entry - stop) * size * multiplier if stop is not None else None
    reward_amt = abs(target - entry) * size * multiplier if target is not None else None
    cost = cost_amount(entry, size, multiplier, spread_bps, commission)
    rr = r_multiple(entry, stop, target)
    be = (breakeven_winrate(risk_amt, reward_amt, cost)
          if (risk_amt is not None and reward_amt is not None) else None)
    be_no_cost = (breakeven_winrate(risk_amt, reward_amt, 0.0)
                  if (risk_amt is not None and reward_amt is not None) else None)
    return {
        "risk_amount": risk_amt, "reward_amount": reward_amt, "cost_amount": cost,
        "rr": rr, "breakeven_winrate": be, "breakeven_winrate_no_cost": be_no_cost,
    }


# --- scenario ladder -------------------------------------------------
def pnl_at(price: float, entry: float, direction: str, size: float, multiplier: float) -> float:
    return (price - entry) * size * multiplier * _sign(direction)


def scenario_ladder(*, entry: float, stop: float | None, target: float | None,
                    atr: float | None, direction: str, size: float,
                    multiplier: float) -> list[dict]:
    """P&L at ±0.5/1/2 ATR, at stop and target, and at a gap THROUGH the stop."""
    rows: list[dict] = []
    sgn = _sign(direction)
    if atr and atr > 0:
        for k in (2.0, 1.0, 0.5):
            for s in (sgn, -sgn):          # favourable then adverse
                price = entry + s * k * atr
                label = f"{'+' if s * sgn > 0 else '−'}{k:g} ATR"
                rows.append({"label": label, "price": price,
                             "pnl": pnl_at(price, entry, direction, size, multiplier)})
    if stop is not None:
        rows.append({"label": "stop", "price": stop, "kind": "stop",
                     "pnl": pnl_at(stop, entry, direction, size, multiplier)})
        if atr and atr > 0:                # gap THROUGH the stop (direct-bet worst case)
            gap = stop - sgn * atr
            rows.append({"label": "gap oltre lo stop (−1 ATR)", "price": gap, "kind": "gap",
                         "pnl": pnl_at(gap, entry, direction, size, multiplier)})
    if target is not None:
        rows.append({"label": "target", "price": target, "kind": "target",
                     "pnl": pnl_at(target, entry, direction, size, multiplier)})
    return rows


# --- defined-risk option illustration (BS long call/put) -------------
def bs_price(kind: str, S: float, K: float, T: float, r: float, sigma: float) -> float | None:
    if not (S > 0 and K > 0 and T > 0 and sigma > 0):
        return None
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    disc = math.exp(-r * T)
    if kind == "call":
        return S * norm_cdf(d1) - K * disc * norm_cdf(d2)
    return K * disc * norm_cdf(-d2) - S * norm_cdf(-d1)


def bs_theta_daily(kind: str, S: float, K: float, T: float, r: float, sigma: float) -> float | None:
    if not (S > 0 and K > 0 and T > 0 and sigma > 0):
        return None
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    term = -(S * norm_pdf(d1) * sigma) / (2.0 * math.sqrt(T))
    disc = math.exp(-r * T)
    if kind == "call":
        theta_year = term - r * K * disc * norm_cdf(d2)
    else:
        theta_year = term + r * K * disc * norm_cdf(-d2)
    return theta_year / 365.0


def option_illustration(*, spot: float, strike: float, direction: str, T: float,
                        r: float, sigma: float, target: float | None,
                        contract_size: float = 1.0) -> dict | None:
    """A long call (for long) / long put (for short) at `strike`: max loss = premium,
    POP = terminal implied prob past break-even, R:R to the user's target, theta.
    An ILLUSTRATION priced with the implied IV — not the live desk chain."""
    kind = "call" if direction == "long" else "put"
    prem = bs_price(kind, spot, strike, T, r, sigma)
    if prem is None:
        return None
    breakeven = strike + prem if kind == "call" else strike - prem
    if kind == "call":
        pop = norm_cdf((math.log(spot / breakeven) + (r - 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))) if breakeven > 0 else None
    else:
        pop = 1.0 - norm_cdf((math.log(spot / breakeven) + (r - 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))) if breakeven > 0 else None
    max_loss = prem * contract_size
    rr = None
    if target is not None and prem > 0:
        gain = max((target - breakeven), 0.0) if kind == "call" else max((breakeven - target), 0.0)
        rr = gain / prem
    return {
        "kind": kind, "strike": strike, "premium": prem, "breakeven": breakeven,
        "max_loss": max_loss, "pop": pop, "rr_to_target": rr,
        "theta_daily": bs_theta_daily(kind, spot, strike, T, r, sigma),
        "note": "Illustrazione a rischio definito (BS con IV implicita, prob a scadenza). Il desk Options ha le catene reali.",
    }


# --- verdict (numbers + 'the decision is yours', never buy/sell) -----
def verdict(breakeven_wr: float | None, implied_hit: float | None) -> dict:
    """Compare the cost-adjusted break-even win rate with the market's implied odds
    of reaching the target. States the edge is the user's THESIS. No call to act."""
    if breakeven_wr is None or implied_hit is None:
        return {"edge": None,
                "text": "Dati insufficienti per il confronto (servono stop, target e odds impliciti)."}
    edge = implied_hit - breakeven_wr
    return {
        "breakeven_winrate": breakeven_wr, "implied_hit": implied_hit, "edge": edge,
        "text": (
            f"Per andare in pari ti serve ragione il {breakeven_wr * 100:.0f}% delle volte "
            f"(costi inclusi). Il mercato prezza ~{implied_hit * 100:.0f}% che il prezzo tocchi "
            "il tuo target (approssimazione a scadenza, non first-touch). "
            + ("Gli odds impliciti sono già SOPRA il tuo pareggio: il margine dipende comunque dalla tua tesi e dai costi."
               if edge > 0 else
               "Gli odds impliciti sono SOTTO il tuo pareggio: senza una tesi per cui il mercato sbaglia, "
               "il valore atteso è ~zero prima dei costi, negativo dopo.")
        ),
        "disclaimer": "Nessun EV previsto: solo odds impliciti + aritmetica del payoff. La decisione è tua.",
    }

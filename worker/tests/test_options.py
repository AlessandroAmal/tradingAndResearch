"""Serious tests for the options quant layer (M5 — the core).

Known-value Black-Scholes, IV solver round-trip, Greek signs/magnitudes,
implied probabilities, and payoff/breakeven/max-loss/R-R for every structure.
"""
import math

import pytest

from app.options import (
    bs_price,
    collar,
    greeks,
    implied_vol,
    payoff_curve,
    prob_above,
    prob_below,
    probability_of_profit,
    protective_put,
    single_leg,
    structure_pnl,
    vertical_spread,
)

# Textbook case: S=K=100, T=1, r=5%, sigma=20%.
S, K, T, R, SIG = 100.0, 100.0, 1.0, 0.05, 0.20


# --- Black-Scholes price ---------------------------------------------
def test_bs_price_known_values():
    assert math.isclose(bs_price("call", S, K, T, R, SIG), 10.4506, abs_tol=1e-3)
    assert math.isclose(bs_price("put", S, K, T, R, SIG), 5.5735, abs_tol=1e-3)


def test_put_call_parity():
    c = bs_price("call", S, K, T, R, SIG)
    p = bs_price("put", S, K, T, R, SIG)
    # c - p == S - K e^{-rT}
    assert math.isclose(c - p, S - K * math.exp(-R * T), abs_tol=1e-6)


def test_bs_price_intrinsic_at_expiry():
    assert bs_price("call", 110, 100, 0, R, SIG) == 10.0
    assert bs_price("put", 90, 100, 0, R, SIG) == 10.0


# --- implied vol solver ----------------------------------------------
def test_iv_round_trip_call_and_put():
    for ot in ("call", "put"):
        price = bs_price(ot, S, K, T, R, 0.27)
        iv = implied_vol(ot, price, S, K, T, R)
        assert iv is not None and math.isclose(iv, 0.27, abs_tol=1e-4)


def test_iv_none_below_intrinsic():
    # A call can't trade below its (discounted) intrinsic -> no IV.
    assert implied_vol("call", 0.01, 150, 100, T, R) is None
    assert implied_vol("call", -1, S, K, T, R) is None


# --- Greeks -----------------------------------------------------------
def test_greek_signs_and_magnitudes():
    gc = greeks("call", S, K, T, R, SIG)
    gp = greeks("put", S, K, T, R, SIG)
    assert 0 < gc["delta"] < 1 and -1 < gp["delta"] < 0
    # call delta - put delta == 1 (parity)
    assert math.isclose(gc["delta"] - gp["delta"], 1.0, abs_tol=1e-6)
    assert gc["gamma"] > 0 and math.isclose(gc["gamma"], gp["gamma"], abs_tol=1e-9)
    assert gc["vega"] > 0 and math.isclose(gc["vega"], gp["vega"], abs_tol=1e-9)
    assert gc["theta"] < 0          # long call decays
    assert gc["rho"] > 0 and gp["rho"] < 0


# --- implied probabilities -------------------------------------------
def test_prob_above_below_complement_and_bounds():
    pa = prob_above(S, 110, T, R, SIG)
    pb = prob_below(S, 110, T, R, SIG)
    assert 0 < pa < 1 and math.isclose(pa + pb, 1.0, abs_tol=1e-9)
    # Higher strike -> lower prob of finishing above it.
    assert prob_above(S, 120, T, R, SIG) < prob_above(S, 100, T, R, SIG)


# --- structures -------------------------------------------------------
def test_single_long_call():
    m = single_leg("call", "long", 100, 5)
    assert m.max_loss == 5 and m.max_gain is None
    assert m.breakeven == 105 and m.profit_side == "above"


def test_single_long_put():
    m = single_leg("put", "long", 100, 6)
    assert m.max_loss == 6 and m.max_gain == 94
    assert m.breakeven == 94 and m.profit_side == "below"


def test_single_short_call():
    m = single_leg("call", "short", 100, 5)
    assert m.max_loss is None and m.max_gain == 5 and m.profit_side == "below"


def test_bull_call_debit_spread():
    m = vertical_spread("call", 100, 5, 110, 2)  # debit 3, width 10
    assert m.net_cost == 3
    assert m.max_loss == 3 and m.max_gain == 7
    assert m.breakeven == 103 and m.profit_side == "above"
    assert math.isclose(m.risk_reward, 7 / 3)


def test_call_credit_spread_breakeven():
    # short 100 call (recv 5), long 110 call (pay 2) -> credit 3
    m = vertical_spread("call", 110, 2, 100, 5)
    assert math.isclose(m.net_cost, -3)
    assert m.max_gain == 3 and m.max_loss == 7
    assert m.breakeven == 103 and m.profit_side == "below"


def test_bear_put_debit_spread():
    m = vertical_spread("put", 100, 6, 90, 3)  # debit 3
    assert m.max_loss == 3 and m.max_gain == 7
    assert m.breakeven == 97 and m.profit_side == "below"


def test_protective_put_floor_and_payoff():
    # own at 100, buy 95 put for 3 -> floor P&L = 95-100-3 = -8
    m = protective_put(100, 95, 3, qty=1)
    assert m.max_loss == 8 and m.max_gain is None
    assert m.breakeven == 103 and m.profit_side == "above"
    # below the strike, P&L is flat at the floor
    assert math.isclose(structure_pnl(m.legs, 80), -8)
    assert math.isclose(structure_pnl(m.legs, 90), -8)
    # above breakeven, profitable
    assert structure_pnl(m.legs, 110) > 0


def test_collar_bounded_both_sides():
    # own at 100, long 95 put @3, short 110 call @2 -> net debit 1
    m = collar(100, 95, 3, 110, 2, qty=1)
    assert math.isclose(m.net_cost, 1)
    # floor: 95-100-1 = -6 ; cap: 110-100-1 = 9
    assert m.max_loss == 6 and m.max_gain == 9
    assert m.breakeven == 101
    assert math.isclose(structure_pnl(m.legs, 80), -6)   # floored
    assert math.isclose(structure_pnl(m.legs, 130), 9)   # capped


def test_payoff_curve_shape():
    legs = single_leg("call", "long", 100, 5).legs
    curve = payoff_curve(legs, 80, 120, steps=5)
    assert len(curve) == 5
    assert curve[0]["pnl"] == -5            # far OTM -> lose premium
    assert math.isclose(curve[-1]["pnl"], 15)  # S=120 -> 20-5


def test_pop_uses_breakeven_and_side():
    m = single_leg("call", "long", 100, 5)  # breakeven 105, above
    pop = probability_of_profit(m, S, T, R, SIG)
    assert pop is not None and math.isclose(pop, prob_above(S, 105, T, R, SIG))

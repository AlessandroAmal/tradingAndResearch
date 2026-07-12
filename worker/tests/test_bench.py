"""Decision bench arithmetic — R:R, cost-adjusted break-even win rate, scenarios,
BS option illustration, verdict. No fabricated probability."""
import math

from pytest import approx

from app.decision.bench import (
    bet_math,
    breakeven_winrate,
    bs_price,
    cost_amount,
    option_illustration,
    r_multiple,
    scenario_ladder,
    verdict,
)


def test_rr_and_breakeven_without_costs():
    # entry 100, stop 98 (risk 2), target 106 (reward 6) -> R:R 3, breakeven 1/(1+3)=25%
    assert r_multiple(100, 98, 106) == approx(3.0)
    assert breakeven_winrate(2.0, 6.0, 0.0) == approx(0.25)


def test_breakeven_rises_with_costs():
    # add cost -> you need to be right MORE often just to break even
    be0 = breakeven_winrate(1000, 3000, 0)
    be1 = breakeven_winrate(1000, 3000, 200)     # (1000+200)/4000 = 0.30
    assert be0 == approx(0.25) and be1 == approx(0.30) and be1 > be0


def test_cost_amount_spread_plus_commission():
    # notional 100*10*1 = 1000; 5 bps -> 0.5; +2 commission -> 2.5
    assert cost_amount(100, 10, 1, spread_bps=5, commission=2) == approx(2.5)


def test_bet_math_bundles_currency_and_ratio():
    m = bet_math(entry=2000, stop=1980, target=2060, size=1, multiplier=100,
                 spread_bps=5, commission=0)
    assert m["risk_amount"] == approx(2000.0)     # 20 * 1 * 100
    assert m["reward_amount"] == approx(6000.0)   # 60 * 1 * 100
    assert m["rr"] == approx(3.0)
    # cost = 2000*100*5/1e4 = 100 -> be = (2000+100)/8000 = 0.2625
    assert m["cost_amount"] == approx(100.0)
    assert m["breakeven_winrate"] == approx(0.2625)
    assert m["breakeven_winrate_no_cost"] == approx(0.25)


def test_scenario_ladder_has_atr_stop_target_and_gap():
    rows = scenario_ladder(entry=100, stop=98, target=106, atr=2.0, direction="long",
                           size=1, multiplier=100)
    labels = [r["label"] for r in rows]
    assert "stop" in labels and "target" in labels
    assert any("gap" in lb for lb in labels)                  # gap-through-stop present
    stop_row = next(r for r in rows if r["label"] == "stop")
    assert stop_row["pnl"] == approx(-200.0)                  # (98-100)*1*100
    gap_row = next(r for r in rows if r.get("kind") == "gap")
    assert gap_row["pnl"] < stop_row["pnl"]                   # worse than the planned stop
    # short flips the sign
    srows = scenario_ladder(entry=100, stop=102, target=94, atr=2.0, direction="short",
                            size=1, multiplier=100)
    assert next(r for r in srows if r["label"] == "target")["pnl"] == approx(600.0)


def test_bs_price_put_call_parity():
    S, K, T, r, sig = 100, 100, 0.25, 0.04, 0.2
    c = bs_price("call", S, K, T, r, sig)
    p = bs_price("put", S, K, T, r, sig)
    # C - P = S - K e^{-rT}
    assert (c - p) == approx(S - K * math.exp(-r * T), abs=1e-9)
    assert bs_price("call", 100, 100, 0, r, sig) is None       # no time -> None


def test_option_illustration_defined_risk():
    ill = option_illustration(spot=100, strike=100, direction="long", T=0.1, r=0.04,
                              sigma=0.3, target=110, contract_size=1)
    assert ill["kind"] == "call" and ill["premium"] > 0
    assert ill["max_loss"] == approx(ill["premium"])           # long option: max loss = premium
    assert 0 < ill["pop"] < 1 and ill["theta_daily"] < 0       # long option bleeds theta
    assert ill["breakeven"] == approx(100 + ill["premium"])


def test_verdict_states_edge_and_thesis_no_call_to_act():
    v = verdict(0.34, 0.41)          # market prices above your breakeven
    assert v["edge"] == approx(0.07) and "34%" in v["text"] and "41%" in v["text"]
    assert "tua" in v["disclaimer"].lower()
    # no directional buy/sell language
    blob = (v["text"] + v["disclaimer"]).lower()
    assert "compra" not in blob and "vendi" not in blob
    neg = verdict(0.5, 0.4)
    assert neg["edge"] < 0 and "valore atteso" in neg["text"].lower()
    assert verdict(None, 0.4)["edge"] is None

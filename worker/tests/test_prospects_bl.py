"""Breeden-Litzenberger risk-neutral density — recovers BS probabilities from a
synthetic constant-IV chain; CDF valid/monotone; thin chain -> low reliability."""
import math
from dataclasses import dataclass

from pytest import approx

from app import options as opt
from app.prospects import bl


@dataclass
class Q:
    option_type: str
    strike: float
    bid: float | None
    ask: float | None
    last: float | None


def _chain(spot, T, r, sigma, strikes):
    """A perfectly-priced BS chain at constant IV (bid=ask=fair, tight)."""
    qs = []
    for k in strikes:
        for kind in ("call", "put"):
            px = opt.bs_price(kind, spot, k, T, r, sigma)
            qs.append(Q(kind, k, bid=px * 0.999, ask=px * 1.001, last=px))
    return qs


def test_bl_recovers_lognormal_cdf():
    spot, T, r, sigma = 100.0, 0.25, 0.02, 0.20
    strikes = [round(s, 1) for s in _linspace(70, 130, 25)]
    dens = bl.risk_neutral_density(_chain(spot, T, r, sigma, strikes), spot, T, r)
    assert dens["quality"]["reliable"] is True
    # analytic risk-neutral P(S_T <= K) for GBM: N(-d2)
    for K in (90.0, 100.0, 110.0):
        d2 = (math.log(spot / K) + (r - 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        analytic_below = opt.norm_cdf(-d2)
        assert bl.prob_below(dens, K) == approx(analytic_below, abs=0.03)


def test_cdf_is_monotone_and_bounded():
    spot, T, r, sigma = 50.0, 0.5, 0.01, 0.30
    dens = bl.risk_neutral_density(_chain(spot, T, r, sigma, _linspace(30, 80, 20)), spot, T, r)
    cdf = dens["cdf"]
    assert cdf[0] >= -1e-9 and cdf[-1] <= 1.0 + 1e-9
    assert all(cdf[i + 1] >= cdf[i] - 1e-9 for i in range(len(cdf) - 1))   # non-decreasing
    # median ~ spot·e^{(r-σ²/2)T}
    assert bl.percentile(dens, 0.5) == approx(spot * math.exp((r - 0.5 * sigma ** 2) * T), rel=0.03)


def test_prob_above_below_complementary():
    spot, T, r, sigma = 100.0, 0.25, 0.0, 0.25
    dens = bl.risk_neutral_density(_chain(spot, T, r, sigma, _linspace(70, 130, 20)), spot, T, r)
    a, b = bl.prob_above(dens, 105), bl.prob_below(dens, 105)
    assert a + b == approx(1.0, abs=1e-6)


def test_summary_intervals_ordered():
    spot, T, r, sigma = 200.0, 1.0, 0.03, 0.22
    dens = bl.risk_neutral_density(_chain(spot, T, r, sigma, _linspace(120, 320, 25)), spot, T, r)
    s = bl.summary(dens, level=210)
    assert s["p2_5"] < s["p16"] < s["median"] < s["p84"] < s["p97_5"]
    assert 0 <= s["prob_above"] <= 1 and "risk-neutral" in s["note"]


def test_thin_chain_flagged_unreliable():
    spot, T, r, sigma = 100.0, 0.25, 0.02, 0.2
    dens = bl.risk_neutral_density(_chain(spot, T, r, sigma, [95, 100, 105])[:4], spot, T, r)
    assert dens["quality"]["reliable"] is False


def _linspace(a, b, n):
    return [a + (b - a) * i / (n - 1) for i in range(n)]


def test_return_summary_is_proxy_agnostic_and_near_zero_short_horizon():
    """The unit-bug guard: a proxy chain (e.g. GLD ~400) yields RETURNS near 0 at
    short horizon, applicable to ANY instrument spot (e.g. GC=F ~4437)."""
    proxy_spot, T, r, sigma = 400.0, 5 / 365, 0.02, 0.15   # 1 week
    dens = bl.risk_neutral_density(_chain(proxy_spot, T, r, sigma, _linspace(320, 480, 25)), proxy_spot, T, r)
    rs = bl.return_summary(dens)
    assert rs["available"] and rs["proxy_spot"] == approx(proxy_spot)
    # median RETURN ~ 0 (risk-neutral, 1 week) -> within ±2% as the spec requires
    assert abs(rs["median_ret"]) <= 0.02
    # applying to an instrument spot 11x larger stays sane (a return, not a level)
    instrument_spot = 4437.30
    implied_median_level = instrument_spot * (1 + rs["median_ret"])
    assert implied_median_level == approx(instrument_spot, rel=0.02)
    assert rs["p2_5_ret"] < rs["p16_ret"] < rs["median_ret"] < rs["p84_ret"] < rs["p97_5_ret"]


def test_prob_above_return_matches_level_query():
    spot, T, r, sigma = 400.0, 0.25, 0.0, 0.2
    dens = bl.risk_neutral_density(_chain(spot, T, r, sigma, _linspace(280, 520, 25)), spot, T, r)
    # P(return >= +5%) must equal P(price >= spot*1.05)
    assert bl.prob_above_return(dens, 0.05) == approx(bl.prob_above(dens, spot * 1.05), abs=1e-9)

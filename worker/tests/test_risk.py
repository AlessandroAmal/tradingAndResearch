"""Serious tests for the risk/sizing math (M6 — must be correct).

Known-value checks for sizing, open risk, heat, R-multiple, P&L, and
breach detection, including multipliers, the short side, and edge cases.
"""
import math
from datetime import date

import pytest

from app.risk import (
    PortfolioRisk,
    PositionRisk,
    evaluate_portfolio,
    evaluate_position,
    open_risk,
    pct_of_account,
    portfolio_heat,
    position_size,
    r_multiple_potential,
    stop_breached,
    unrealized_pnl,
)


# --- sizing -----------------------------------------------------------
def test_position_size_basic():
    # 1% of 100k = 1000 risk; entry 100, stop 95 -> 5/pt -> size 200
    assert position_size(100_000, 1.0, 100, 95, 1.0) == 200.0


def test_position_size_with_multiplier():
    # multiplier 10 -> 5*10 = 50/unit -> 1000/50 = 20
    assert position_size(100_000, 1.0, 100, 95, 10.0) == 20.0


def test_position_size_degenerate_returns_none():
    assert position_size(100_000, 1.0, 100, 100, 1.0) is None  # entry == stop
    assert position_size(100_000, 1.0, 100, None, 1.0) is None  # no stop
    assert position_size(0, 1.0, 100, 95, 1.0) is None          # no account
    assert position_size(100_000, 0, 100, 95, 1.0) is None      # no risk


# --- open risk / pct --------------------------------------------------
def test_open_risk_and_pct():
    r = open_risk(100, 95, 200, 1.0)
    assert r == 1000.0
    assert math.isclose(pct_of_account(r, 100_000), 1.0)


def test_open_risk_none_without_stop():
    assert open_risk(100, None, 200) is None
    assert pct_of_account(None, 100_000) is None


# --- R-multiple -------------------------------------------------------
def test_r_multiple_potential():
    # entry 100, stop 95, target 115 -> 15/5 = 3R
    assert r_multiple_potential(100, 95, 115) == 3.0


def test_r_multiple_none_cases():
    assert r_multiple_potential(100, 100, 115) is None  # zero risk
    assert r_multiple_potential(100, 95, None) is None


# --- unrealized P&L ---------------------------------------------------
def test_unrealized_pnl_long_and_short():
    assert unrealized_pnl(110, 100, 200, "long", 1.0) == 2000.0
    assert unrealized_pnl(110, 100, 200, "short", 1.0) == -2000.0


def test_unrealized_pnl_with_multiplier_and_no_price():
    assert unrealized_pnl(110, 100, 20, "long", 10.0) == 2000.0
    assert unrealized_pnl(None, 100, 200, "long") is None


# --- portfolio heat ---------------------------------------------------
def test_portfolio_heat_ignores_none():
    assert portfolio_heat([1000, 500, None, 250]) == 1750.0


# --- stop breach ------------------------------------------------------
def test_stop_breached_long_short():
    assert stop_breached(94, 95, "long") is True
    assert stop_breached(96, 95, "long") is False
    assert stop_breached(106, 105, "short") is True
    assert stop_breached(104, 105, "short") is False
    assert stop_breached(None, 95, "long") is False  # no price -> no breach


# --- evaluate_position (integration of the above) ---------------------
def test_evaluate_position_full():
    pr = evaluate_position(
        side="long", entry=100, stop=95, target=115, size=200,
        current_price=110, account_size=100_000, max_risk_per_trade_pct=1.0,
        multiplier=1.0, deadline=date(2026, 7, 1), today=date(2026, 6, 21),
        deadline_warn_days=3,
    )
    assert isinstance(pr, PositionRisk)
    assert pr.open_risk == 1000.0
    assert math.isclose(pr.open_risk_pct, 1.0)
    assert pr.r_multiple == 3.0
    assert pr.unrealized_pnl == 2000.0
    assert pr.days_to_deadline == 10
    assert pr.stop_breached is False
    assert pr.risk_per_trade_breached is False  # exactly at limit, not over
    assert pr.deadline_near is False


def test_evaluate_position_breaches():
    # Oversized: risks 2% (> 1% limit); price below stop; deadline in 2 days.
    pr = evaluate_position(
        side="long", entry=100, stop=95, target=115, size=400,
        current_price=94, account_size=100_000, max_risk_per_trade_pct=1.0,
        deadline=date(2026, 6, 23), today=date(2026, 6, 21), deadline_warn_days=3,
    )
    assert pr.risk_per_trade_breached is True
    assert pr.stop_breached is True
    assert pr.deadline_near is True
    assert pr.days_to_deadline == 2


# --- evaluate_portfolio ----------------------------------------------
def test_evaluate_portfolio_within_limits():
    pf = evaluate_portfolio(
        open_risks=[1000, 1500, 500], account_size=100_000,
        max_portfolio_heat_pct=6.0, max_concurrent_positions=8, open_count=3,
    )
    assert isinstance(pf, PortfolioRisk)
    assert pf.heat == 3000.0
    assert math.isclose(pf.heat_pct, 3.0)
    assert pf.heat_breached is False
    assert pf.positions_breached is False


def test_evaluate_portfolio_breached():
    pf = evaluate_portfolio(
        open_risks=[5000, 3000], account_size=100_000,
        max_portfolio_heat_pct=6.0, max_concurrent_positions=1, open_count=2,
    )
    assert math.isclose(pf.heat_pct, 8.0)
    assert pf.heat_breached is True       # 8% > 6%
    assert pf.positions_breached is True  # 2 > 1

"""Risk & position-sizing math (M6 — the brief's core, must be correct).

Pure functions over numbers — no I/O — so they are exhaustively unit-tested
(`worker/tests/test_risk.py`). This is a READ-ONLY cockpit: sizing is a
CALCULATOR and breach detection produces FLAGS only — nothing here places
or implies an order.

Conventions:
  - `risk_pct` and all *_pct values are PERCENTAGES (1.0 == 1%).
  - `multiplier` is the contract/point value (default 1.0).
  - `side` is 'long' or 'short'.
  - Functions return None when inputs are insufficient/degenerate, so the
    dashboard can degrade gracefully rather than show wrong numbers.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date


# --- sizing -----------------------------------------------------------
def position_size(
    account_size: float,
    risk_pct: float,
    entry: float,
    stop: float | None,
    multiplier: float = 1.0,
) -> float | None:
    """Size that risks exactly `risk_pct`% of the account from entry to stop.

    size = (account_size * risk_pct/100) / (|entry - stop| * multiplier)
    """
    if stop is None or account_size <= 0 or risk_pct <= 0 or multiplier <= 0:
        return None
    per_unit = abs(entry - stop) * multiplier
    if per_unit <= 0:
        return None
    risk_amount = account_size * (risk_pct / 100.0)
    return risk_amount / per_unit


# --- risk per position ------------------------------------------------
def open_risk(
    entry: float, stop: float | None, size: float, multiplier: float = 1.0
) -> float | None:
    """Currency at risk if the stop is hit: |entry - stop| * size * multiplier."""
    if stop is None:
        return None
    return abs(entry - stop) * size * multiplier


def pct_of_account(amount: float | None, account_size: float) -> float | None:
    """Express a currency amount as a percentage of the account."""
    if amount is None or account_size <= 0:
        return None
    return amount / account_size * 100.0


def r_multiple_potential(
    entry: float, stop: float | None, target: float | None
) -> float | None:
    """Potential reward/risk in R: |target - entry| / |entry - stop|."""
    if stop is None or target is None:
        return None
    risk = abs(entry - stop)
    if risk == 0:
        return None
    return abs(target - entry) / risk


def unrealized_pnl(
    current_price: float | None,
    entry: float,
    size: float,
    side: str,
    multiplier: float = 1.0,
) -> float | None:
    """Unrealised P&L: (current - entry) * size * sign(side) * multiplier."""
    if current_price is None:
        return None
    sign = 1.0 if side == "long" else -1.0
    return (current_price - entry) * size * sign * multiplier


# --- portfolio --------------------------------------------------------
def portfolio_heat(open_risks: Sequence[float | None]) -> float:
    """Total open risk (currency) across positions; None risks are ignored."""
    return sum(r for r in open_risks if r is not None)


# --- breach detection (FLAGS only — no dispatch; Telegram is M8) -------
def stop_breached(current_price: float | None, stop: float | None, side: str) -> bool:
    """True when price has punched through the stop (long: <=, short: >=)."""
    if current_price is None or stop is None:
        return False
    return current_price <= stop if side == "long" else current_price >= stop


@dataclass(frozen=True)
class PositionRisk:
    open_risk: float | None
    open_risk_pct: float | None
    r_multiple: float | None
    unrealized_pnl: float | None
    days_to_deadline: int | None
    stop_breached: bool
    risk_per_trade_breached: bool
    deadline_near: bool


def evaluate_position(
    *,
    side: str,
    entry: float,
    stop: float | None,
    target: float | None,
    size: float,
    current_price: float | None,
    account_size: float,
    max_risk_per_trade_pct: float,
    multiplier: float = 1.0,
    deadline: date | None = None,
    today: date | None = None,
    deadline_warn_days: int = 3,
) -> PositionRisk:
    orisk = open_risk(entry, stop, size, multiplier)
    orisk_pct = pct_of_account(orisk, account_size)
    rmult = r_multiple_potential(entry, stop, target)
    pnl = unrealized_pnl(current_price, entry, size, side, multiplier)
    sbreach = stop_breached(current_price, stop, side)
    rpt_breach = orisk_pct is not None and orisk_pct > max_risk_per_trade_pct

    dtd: int | None = None
    if deadline is not None and today is not None:
        dtd = (deadline - today).days
    dnear = dtd is not None and dtd <= deadline_warn_days

    return PositionRisk(
        open_risk=orisk,
        open_risk_pct=orisk_pct,
        r_multiple=rmult,
        unrealized_pnl=pnl,
        days_to_deadline=dtd,
        stop_breached=sbreach,
        risk_per_trade_breached=rpt_breach,
        deadline_near=dnear,
    )


@dataclass(frozen=True)
class PortfolioRisk:
    heat: float
    heat_pct: float | None
    open_count: int
    heat_breached: bool
    positions_breached: bool


def evaluate_portfolio(
    *,
    open_risks: Sequence[float | None],
    account_size: float,
    max_portfolio_heat_pct: float,
    max_concurrent_positions: int,
    open_count: int,
) -> PortfolioRisk:
    heat = portfolio_heat(open_risks)
    heat_pct = pct_of_account(heat, account_size)
    heat_breach = heat_pct is not None and heat_pct > max_portfolio_heat_pct
    pos_breach = open_count > max_concurrent_positions
    return PortfolioRisk(
        heat=heat,
        heat_pct=heat_pct,
        open_count=open_count,
        heat_breached=heat_breach,
        positions_breached=pos_breach,
    )

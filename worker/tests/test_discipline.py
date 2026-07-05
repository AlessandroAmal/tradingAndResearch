"""Discipline trackers — set-aside, committed-budget windows, 2/3 exit guide.
Pure math, no I/O."""
from datetime import date

from pytest import approx

from app.discipline import (
    committed_in_windows,
    exit_guide,
    max_favorable_excursion,
    set_aside_today,
    two_thirds_trigger,
)

TODAY = date(2026, 7, 4)  # a Saturday


# --- profit set-aside (#4) -------------------------------------------
def test_set_aside_caps_at_target():
    trades = [
        {"realized_pnl": 180.0, "closed_at": "2026-07-04"},   # today, win
        {"realized_pnl": -50.0, "closed_at": "2026-07-04"},   # today, loss (ignored)
        {"realized_pnl": 999.0, "closed_at": "2026-07-01"},   # not today (ignored)
    ]
    out = set_aside_today(trades, target=100.0, today=TODAY)
    assert out["realized_profit"] == approx(180.0)
    assert out["set_aside"] == approx(100.0)   # min(profit, target)


def test_set_aside_zero_when_no_profit_today():
    out = set_aside_today([{"realized_pnl": -20.0, "closed_at": "2026-07-04"}], 100.0, TODAY)
    assert out["set_aside"] == 0.0 and out["realized_profit"] == 0.0


# --- committed budget windows (#1) -----------------------------------
def test_committed_in_windows_sums_open_risk_by_window():
    # risk = |entry-stop| * size * mult
    positions = [
        {"entry": 2000, "stop": 1990, "size": 1, "multiplier": 100, "opened_at": "2026-07-04"},  # 1000 today
        {"entry": 100, "stop": 98, "size": 10, "multiplier": 1, "opened_at": "2026-07-01"},       # 20 this week/month, not today
        {"entry": 50, "stop": 45, "size": 2, "multiplier": 1, "opened_at": "2026-06-10"},         # June — outside July
    ]
    out = committed_in_windows(positions, TODAY)
    assert out["day"] == approx(1000.0)
    assert out["week"] == approx(1020.0)     # 2026-07-01 is same ISO week as 07-04
    assert out["month"] == approx(1020.0)    # June position excluded (different month)


def test_committed_skips_positions_without_stop():
    out = committed_in_windows([{"entry": 100, "stop": None, "size": 1, "opened_at": "2026-07-04"}], TODAY)
    assert out == {"day": 0.0, "week": 0.0, "month": 0.0}


# --- 2/3 exit guide (#6) ---------------------------------------------
def test_mfe_long_and_short():
    # long from 100, high 130 -> peak 30*size*mult
    assert max_favorable_excursion("long", 100, 2, 1, [110, 130, 120], [95]) == approx(60.0)
    # short from 100, low 80 -> peak 20*size*mult
    assert max_favorable_excursion("short", 100, 1, 10, [105], [95, 80, 90]) == approx(200.0)
    # never favourable -> 0
    assert max_favorable_excursion("long", 100, 1, 1, [90, 95], [80]) == 0.0


def test_two_thirds_trigger():
    assert two_thirds_trigger(300, 200, 2 / 3) is True    # reached the 2/3 threshold -> take-note
    assert two_thirds_trigger(300, 250, 2 / 3) is False    # still above the threshold
    assert two_thirds_trigger(0, -5) is False              # no positive peak -> never
    assert two_thirds_trigger(None, 100) is False


def test_exit_guide_triggers_after_giveback():
    g = exit_guide("long", 100, 1, 10, highs=[130], lows=[100], current_pnl=150)
    # peak = (130-100)*1*10 = 300; threshold 200; current 150 <= 200 -> triggered
    assert g["peak_pnl"] == approx(300.0) and g["triggered"] is True
    assert g["note"] and "2/3" in g["note"]

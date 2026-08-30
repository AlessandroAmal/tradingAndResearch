"""Quarterly fundamentals: parse_quarterly mapping + trajectory QoQ/YoY +
inflection detection + own-history percentile. Pure fixtures, no network. All
context — no directional number anywhere."""
from pytest import approx

from app.fundamentals_trajectory import compute_trajectory, own_percentile
from app.providers.fundamentals import parse_quarterly


def test_parse_quarterly_maps_and_derives_margins_and_fcf():
    inc = {
        "2026-06-30": {"Total Revenue": 1000, "Net Income": 200, "Gross Profit": 600,
                       "Operating Income": 300, "Diluted EPS": 2.0},
        "2026-03-31": {"Total Revenue": 900, "Net Income": 150, "Gross Profit": 500,
                       "Operating Income": 250, "Diluted EPS": 1.5},
    }
    bal = {"2026-06-30": {"Total Debt": 400, "Cash And Cash Equivalents": 800},
           "2026-03-31": {"Total Debt": 350, "Cash And Cash Equivalents": 700}}
    cf = {"2026-06-30": {"Operating Cash Flow": 350, "Capital Expenditure": -100},
          "2026-03-31": {"Free Cash Flow": 180}}
    rows = parse_quarterly(inc, bal, cf)
    assert [r["period_end"] for r in rows] == ["2026-06-30", "2026-03-31"]   # newest first
    q = rows[0]
    assert q["period_label"] == "2026-Q2"
    assert q["revenue"] == 1000 and q["net_income"] == 200
    assert q["gross_margin"] == approx(0.6) and q["net_margin"] == approx(0.2)
    assert q["fcf"] == approx(250)                 # 350 + (-100)
    assert rows[1]["fcf"] == approx(180)           # explicit Free Cash Flow used
    assert q["debt"] == 400 and q["eps"] == 2.0


def test_parse_quarterly_debt_fallback_and_missing():
    bal = {"2026-06-30": {"Long Term Debt": 300, "Current Debt": 50}}
    rows = parse_quarterly({}, bal, {})
    assert rows[0]["debt"] == 350                  # LT + current fallback
    assert rows[0]["revenue"] is None              # missing -> None, no crash


def _hist():
    # newest first: 5 quarters so YoY (4 back) exists
    return [
        {"period_label": "2026-Q2", "period_end": "2026-06-30", "revenue": 1200, "net_margin": 0.18, "fcf": 300, "debt": 500},
        {"period_label": "2026-Q1", "period_end": "2026-03-31", "revenue": 1100, "net_margin": 0.20, "fcf": -50, "debt": 480},
        {"period_label": "2025-Q4", "period_end": "2025-12-31", "revenue": 1050, "net_margin": 0.19, "fcf": 200, "debt": 300},
        {"period_label": "2025-Q3", "period_end": "2025-09-30", "revenue": 1000, "net_margin": 0.17, "fcf": 150, "debt": 250},
        {"period_label": "2025-Q2", "period_end": "2025-06-30", "revenue": 1000, "net_margin": 0.15, "fcf": 100, "debt": 240},
    ]


def test_trajectory_qoq_and_yoy():
    t = compute_trajectory(_hist())
    rev = t["metrics"]["revenue"]
    assert rev["current"] == 1200
    assert rev["qoq"]["abs"] == 100 and rev["qoq"]["rel"] == approx(100 / 1100)
    assert rev["yoy"]["abs"] == 200 and rev["yoy"]["rel"] == approx(0.2)   # vs 2025-Q2 (1000)
    assert rev["sparkline"] == [1000, 1000, 1050, 1100, 1200]              # oldest→newest
    nm = t["metrics"]["net_margin"]
    assert nm["kind"] == "ratio" and nm["qoq"]["rel"] is None              # ratios: points only
    assert nm["qoq"]["abs"] == approx(-0.02)


def test_trajectory_flags_fcf_sign_flip_and_debt_acceleration():
    t = compute_trajectory(_hist())
    # FCF went -50 (Q1) -> +300 (Q2): flip back to positive
    assert t["metrics"]["fcf"]["inflection"] is True
    assert "positivo" in t["metrics"]["fcf"]["inflection_note"]
    # debt: 250 -> 300 (+50) then 480 -> 500 ... series ascending; last jump 480->500=20
    # acceleration check uses the last three points: 300,480,500 -> d_now=20, d_prev=180 -> not accel
    # so build an accelerating case:
    accel = [
        {"period_label": "Q3", "debt": 800}, {"period_label": "Q2", "debt": 600},
        {"period_label": "Q1", "debt": 550}, {"period_label": "Q0", "debt": 540},
    ]
    td = compute_trajectory(accel)
    assert td["metrics"]["debt"]["inflection"] is True
    assert "accelerando" in td["metrics"]["debt"]["inflection_note"]


def test_own_percentile_needs_min_history():
    assert own_percentile([10, 12, 15], 14)["percentile"] is None      # < 8 points
    vals = [10, 11, 12, 13, 14, 15, 16, 17, 18, 40]
    r = own_percentile(vals, 17)
    assert r["percentile"] == approx(0.8) and r["band"] == "cara"
    assert own_percentile(vals, None)["percentile"] is None

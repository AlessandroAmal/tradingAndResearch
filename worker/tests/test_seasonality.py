"""Ciclicità — honest seasonality: n always shown, min-sample gate, caveat,
'insufficient' + 'no significant pattern' cases. No directional number."""
from datetime import date, timedelta

from app.decision.seasonality import (
    SEASONALITY_CAVEAT,
    compute_seasonality,
    monthly_seasonality,
    weekday_seasonality,
)


def _daily_series(years: int, start=date(2010, 1, 1)):
    """A flat daily series (weekdays only) — NO seasonality by construction, so
    nothing can be flagged significant (zero within-bucket variance)."""
    dates, closes = [], []
    d = start
    for _ in range(years * 365):
        if d.weekday() < 5:
            dates.append(d.isoformat())
            closes.append(100.0)             # constant -> returns all 0
        d += timedelta(days=1)
    return dates, closes


def test_monthly_buckets_have_n_and_no_conclusion_below_threshold():
    dates, closes = _daily_series(3)                 # ~3 yrs -> ~2-3 obs per month
    buckets = monthly_seasonality(dates, closes, min_sample=8)
    assert len(buckets) == 12
    for b in buckets:
        assert "n" in b and "mean_return" in b and "pct_up" in b
        assert b["sufficient"] is False              # < 8 years -> insufficient
        assert b["significant"] is False             # never significant when insufficient


def test_weekday_buckets_sufficient_with_enough_history():
    dates, closes = _daily_series(2)                 # ~100 obs per weekday
    wd = weekday_seasonality(dates, closes, min_sample=30)
    assert len(wd) == 5 and all(b["n"] >= 30 and b["sufficient"] for b in wd)


def test_compute_flags_no_significant_pattern():
    dates, closes = _daily_series(12)
    s = compute_seasonality(dates, closes)
    assert s["available"] is True and s["years"] and s["years"] > 10
    assert s["caveat"] == SEASONALITY_CAVEAT
    # flat series -> nothing should be flagged significant, and we say so
    assert s["any_significant"] is False and "Nessun pattern" in s["note"]
    # no directional probability field anywhere
    import json
    assert "prob_up" not in json.dumps(s)


def test_insufficient_history_is_honest():
    s = compute_seasonality(["2026-01-01"], [100.0])
    assert s["available"] is False and "insufficiente" in s["note"].lower()
    assert s["caveat"] == SEASONALITY_CAVEAT


def test_real_monthly_signal_is_detected_but_gated_by_n():
    # Engineer a strong "December up" so a bucket COULD be significant with enough n.
    dates, closes, c = [], [], 100.0
    d = date(2005, 1, 1)
    while d <= date(2025, 12, 31):
        if d.weekday() < 5:
            bump = 1.02 if d.month == 12 else 1.0
            c *= bump ** (1 / 20)   # spread the december move across its days
            dates.append(d.isoformat()); closes.append(c)
        d += timedelta(days=1)
    buckets = monthly_seasonality(dates, closes, min_sample=8)
    dec = buckets[11]
    assert dec["n"] >= 8 and dec["sufficient"] is True
    assert dec["mean_return"] is not None and dec["mean_return"] > 0

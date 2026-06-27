"""Tests for the seeded calendar fallback (recurring macro dates)."""
from datetime import date

from app.providers.calendar.seeded_provider import SeededCalendarProvider

SEED = {
    "events": [
        {"title": "FOMC decision", "rule": "explicit", "importance": "high",
         "dates": ["2026-07-29", "2026-09-16", "2026-12-09"]},
        {"title": "US Nonfarm Payrolls", "rule": "nth_weekday", "n": 1, "weekday": 4},  # 1st Fri
        {"title": "US CPI", "rule": "day_of_month", "day": 12},
        {"title": "US PCE", "rule": "last_business_day"},
    ]
}


def _titles_on(events, d: date):
    return {e.title for e in events if e.event_time.date() == d}


def test_explicit_dates_within_window_only():
    ev = SeededCalendarProvider(SEED).fetch_events("2026-06-26", "2026-08-31")
    fomc = [e for e in ev if e.title == "FOMC decision"]
    dates = {e.event_time.date() for e in fomc}
    assert date(2026, 7, 29) in dates       # in window
    assert date(2026, 9, 16) not in dates    # out of window (after to_date)


def test_nth_weekday_first_friday():
    ev = SeededCalendarProvider(SEED).fetch_events("2026-07-01", "2026-07-31")
    # First Friday of July 2026 is the 3rd.
    assert "US Nonfarm Payrolls" in _titles_on(ev, date(2026, 7, 3))


def test_day_of_month_and_last_business_day():
    ev = SeededCalendarProvider(SEED).fetch_events("2026-06-01", "2026-06-30")
    assert "US CPI" in _titles_on(ev, date(2026, 6, 12))
    # Last business day of June 2026 is Tue 30 June.
    assert "US PCE" in _titles_on(ev, date(2026, 6, 30))


def test_events_sorted_and_in_window():
    ev = SeededCalendarProvider(SEED).fetch_events("2026-07-01", "2026-09-30")
    times = [e.event_time for e in ev]
    assert times == sorted(times)
    assert all(date(2026, 7, 1) <= e.event_time.date() <= date(2026, 9, 30) for e in ev)
    assert all(e.source == "seeded" for e in ev)


def test_empty_seed_returns_nothing():
    assert SeededCalendarProvider({}).fetch_events("2026-07-01", "2026-07-31") == []

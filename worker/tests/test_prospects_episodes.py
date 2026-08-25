"""Multi-year episodes — episodes listed one by one, NO percentage under n<10."""
from app.prospects import episodes as E


def _series(vals, start_year=2000):
    """Yearly closes -> (dates, closes) with a Dec date per year."""
    return [f"{start_year + i}-12-31" for i in range(len(vals))], [float(v) for v in vals]


def test_bull_year_episodes_listed_with_context():
    # up, up, up, down, up, up, up ...
    dates, closes = _series([100, 110, 121, 133, 120, 132, 145, 160])
    res = E.bull_year_episodes(dates, closes, nth=3)
    # 3rd up-year happens at 2002 (100->110->121->133) and again at 2007
    assert res["n"] >= 1
    ep = res["episodes"][0]
    assert "year" in ep and "next_year_return" in ep and ep["run_length"] == 3


def test_no_percentage_under_threshold():
    dates, closes = _series([100, 110, 121, 133])
    res = E.bull_year_episodes(dates, closes, nth=3)
    assert res["n"] < E.MIN_FOR_PCT
    assert res["percentage_allowed"] is False
    assert "non statistica" in res["caveat"]
    # the structure carries NO derived percentage field
    assert "pct" not in res and "probability" not in res


def test_drawdown_episodes_detect_depth_and_forward():
    # ramp to 100, crash to 70 (>20% dd), recover to 110
    closes = [100] * 5 + [95, 88, 80, 72, 70] + [78, 90, 105, 110] + [110] * 260
    dates = [f"2010-01-01" for _ in closes]  # dates unused by dd math except labels
    # give distinct dates so labels differ
    from datetime import date, timedelta
    d0 = date(2010, 1, 1)
    dates = [(d0 + timedelta(days=i)).isoformat() for i in range(len(closes))]
    res = E.drawdown_episodes(dates, closes, threshold=0.20, forward=5)
    assert res["n"] >= 1
    ep = res["episodes"][0]
    assert ep["depth"] <= -0.20 and "trough_date" in ep
    assert res["percentage_allowed"] is (res["n"] >= E.MIN_FOR_PCT)


def test_min_for_pct_gate_on_drawdowns():
    closes = [100, 101, 102]   # no drawdown
    dates = ["2020-01-01", "2020-01-02", "2020-01-03"]
    res = E.drawdown_episodes(dates, closes)
    assert res["n"] == 0 and res["percentage_allowed"] is False

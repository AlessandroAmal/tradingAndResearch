"""FundamentalsProvider parsing + fresh stock news. yfinance/feedparser mocked."""
from pytest import approx

from app.providers.fundamentals import parse_fundamentals
from app.decision import stock_news


def test_parse_full_info():
    info = {
        "trailingPE": 60.0, "forwardPE": 45.0, "priceToSalesTrailing12Months": 25.0, "priceToBook": 40.0,
        "revenueGrowth": 0.55, "earningsGrowth": 0.80,
        "grossMargins": 0.75, "operatingMargins": 0.60, "profitMargins": 0.50, "returnOnEquity": 1.2,
        "freeCashflow": 2.0e10, "operatingCashflow": 3.0e10, "totalCash": 4.0e10, "totalDebt": 1.0e10, "debtToEquity": 25.0,
        "trailingEps": 3.0, "forwardEps": 4.2,
        "targetMeanPrice": 200.0, "numberOfAnalystOpinions": 50, "recommendationKey": "buy", "recommendationMean": 1.8,
    }
    earn = {"next_date": "2026-08-26", "next_eps_estimate": 1.1,
            "surprises": [{"date": "2026-05-20", "reported": 0.96, "estimate": 0.88, "surprise_pct": 9.1, "beat": True}]}
    f = parse_fundamentals(info, earn)
    assert f["valuation"]["pe_forward"] == approx(45.0)
    assert f["growth"]["revenue_yoy"] == approx(0.55)
    assert f["quality"]["roe"] == approx(1.2)
    assert f["cash"]["free_cash_flow"] == approx(2.0e10)
    assert f["earnings"]["next_date"] == "2026-08-26" and f["earnings"]["surprises"][0]["beat"] is True
    assert f["analysts"]["target_mean"] == approx(200.0) and f["analysts"]["recommendation"] == "buy"
    assert "previsione" in f["note"].lower()  # honest label


def test_parse_missing_fields_are_none():
    f = parse_fundamentals({}, None)
    assert f["valuation"]["pe_trailing"] is None
    assert f["growth"]["earnings_yoy"] is None
    assert f["cash"]["debt_to_equity"] is None
    assert f["earnings"]["surprises"] == []
    assert f["analysts"]["target_mean"] is None


def test_parse_handles_nan_and_strings():
    f = parse_fundamentals({"trailingPE": float("nan"), "forwardPE": "n/a", "priceToBook": "12.5"}, None)
    assert f["valuation"]["pe_trailing"] is None   # NaN -> None
    assert f["valuation"]["pe_forward"] is None     # non-numeric -> None
    assert f["valuation"]["pb"] == approx(12.5)      # numeric string coerced


def test_earnings_yoy_falls_back_to_quarterly():
    f = parse_fundamentals({"earningsQuarterlyGrowth": 0.3}, None)
    assert f["growth"]["earnings_yoy"] == approx(0.3)


# --- stock news ------------------------------------------------------
def test_recent_news_parsed(monkeypatch):
    entries = [
        {"title": "Tesla deliveries miss estimates", "link": "http://x/1",
         "published_parsed": None, "source": {"title": "Reuters"}},
        {"title": "NHTSA opens probe into Tesla Autopilot", "link": "http://x/2",
         "published_parsed": None, "source": {"title": "Bloomberg"}},
        {"title": "", "link": "http://x/3"},   # dropped (no title)
    ]
    monkeypatch.setattr(stock_news, "_parse_feed", lambda url: entries)
    out = stock_news.recent_news("Tesla", "TSLA", limit=5)
    titles = [n["title"] for n in out]
    assert "Tesla deliveries miss estimates" in titles
    assert any("NHTSA" in t for t in titles)      # regulatory caught
    assert len(out) == 2 and out[0]["source"] == "Reuters"


def test_recent_news_failure_is_empty(monkeypatch):
    def boom(url):
        raise RuntimeError("feed down")
    monkeypatch.setattr(stock_news, "_parse_feed", boom)
    assert stock_news.recent_news("Tesla", "TSLA") == []


def test_recent_news_needs_terms():
    assert stock_news.recent_news("", "") == []

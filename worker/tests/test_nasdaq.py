"""Nasdaq-100 board + instrument-driven generalization of the desk signals.

EUR/USD must stay identical; the signal modules must take proxy/COT market from
config (no FXE/EUR hardcoded). External sources mocked.
"""
from datetime import date

import app.decision.board as board
from app.config import load_config
from app.ingestion.macro_job import _configured_fred_series
from app.providers.positioning.base import CotReport


def _inst(symbol):
    cfg = load_config()
    return cfg, next(i for i in cfg.decision_board["instruments"] if i["symbol"] == symbol)


def test_nasdaq_config_loaded():
    _, n = _inst("^NDX")
    assert n["options_proxy"] == "QQQ"
    assert n["rsi"] == {"period": 14, "overbought": 70, "oversold": 30}
    assert n["round_step"] == 500
    drivers = {d["id"] for d in n["macro_drivers"]}
    assert {"DFII10", "BAMLH0A0HYM2", "^VIX", "DTWEXBGS"} <= drivers
    assert "DGS10" not in drivers          # no double-count of rate series
    assert n["positioning"]["market"] == "NASDAQ MINI"
    # COT is context-only for an equity index (does not drive the lean).
    assert n["synthesis"]["weights"]["cot"] == 0


def test_eurusd_unchanged():
    _, e = _inst("EURUSD=X")
    assert e["options_proxy"] == "FXE"
    assert e["positioning"]["market"] == "EURO FX"
    main = next(d for d in e["macro_drivers"] if d["id"] == "FED_ECB_SPREAD")
    assert main["weight"] == 1.5


def test_macro_job_fetches_nasdaq_hy_series():
    cfg = load_config()
    ids = _configured_fred_series(cfg, exclude=set())
    assert "BAMLH0A0HYM2" in ids and "DFII10" in ids   # Nasdaq HY spread is fetched


def test_cot_is_instrument_driven_no_hardcoded_market(monkeypatch):
    captured = {}

    class FakeProv:
        name = "fake"
        def fetch_history(self, market, *, lookback_weeks, report="tff"):
            captured["market"] = market
            captured["lookback"] = lookback_weeks
            return [CotReport(report_date=date(2026, 6, 23), long=120, short=80,
                              net=40, open_interest=1000, source="fake")]

    import app.providers.positioning as pos
    monkeypatch.setattr(pos, "build_positioning_provider", lambda name: FakeProv())

    inst = {"positioning": {"provider": "cftc", "market": "NASDAQ MINI",
                            "lookback_weeks": 99, "note": "COT debole sugli indici."}}
    res = board._fx_cot(inst, {})
    assert captured["market"] == "NASDAQ MINI" and captured["lookback"] == 99
    assert "NASDAQ MINI" in res["note"] and "COT debole" in res["note"]
    assert "EURO FX" not in res["note"]    # no hardcoded market leaks in


def test_cot_note_uses_eur_market_for_eurusd(monkeypatch):
    class FakeProv:
        name = "fake"
        def fetch_history(self, market, *, lookback_weeks, report="tff"):
            return [CotReport(report_date=date(2026, 6, 23), long=1, short=1, net=0,
                              open_interest=1, source="fake")]
    import app.providers.positioning as pos
    monkeypatch.setattr(pos, "build_positioning_provider", lambda name: FakeProv())
    res = board._fx_cot({"positioning": {"market": "EURO FX"}}, {})
    assert "EURO FX" in res["note"]        # still correct for EUR/USD

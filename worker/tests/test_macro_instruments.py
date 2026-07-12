"""RAME (copper) + DAX: two macro instruments with DIFFERENT COT caveats.

Copper: COT ON (Disaggregated / Managed Money), CPER options thin.
DAX:    COT OFF (Eurex, not CFTC), EWG proxy approximate.
External sources mocked.
"""
from datetime import date

import app.decision.board as board
from app.config import load_config
from app.providers.positioning.base import CotReport
from app.providers.positioning.cftc_provider import REPORTS, _parse_rows


def _insts():
    cfg = load_config()
    return {i["symbol"]: i for i in cfg.decision_board["instruments"]}


# --- config ----------------------------------------------------------
def test_copper_config_cot_on_disaggregated():
    i = _insts()["HG=F"]
    assert i["name"] == "Rame" and i["options_proxy"] == "CPER"
    pos = i["positioning"]
    assert pos["report"] == "disaggregated"          # commodity report (Managed Money)
    assert "COPPER" in pos["market"]
    assert i["synthesis"]["weights"]["cot"] == 0.6   # COT useful on commodities
    drivers = {d["id"] for d in i["macro_drivers"]}
    assert drivers == {"DTWEXBGS", "DFII10"}         # FRED is context; China via news/PMI
    assert i["figures"] == ["China policy"]


def test_dax_config_cot_off_eurex():
    i = _insts()["^GDAXI"]
    assert i["name"] == "DAX 40" and i["options_proxy"] == "EWG"
    assert "positioning" not in i                     # Eurex -> no CFTC COT
    assert "cot" not in i["synthesis"]["weights"]
    drivers = {d["id"] for d in i["macro_drivers"]}
    assert drivers == {"^VIX", "FED_ECB_SPREAD", "DTWEXBGS"}
    assert i["round_step"] == 250


def test_existing_instruments_unchanged():
    insts = _insts()
    # The original macro/single-stock set is still present unchanged; the book
    # holdings (MSFT/AVGO/VRT/NVO/SPGI) were added on top (single-stock template).
    assert {"GC=F", "EURUSD=X", "^NDX", "NVDA", "TSLA", "GOOGL", "HG=F", "^GDAXI"} <= set(insts)
    assert {"MSFT", "AVGO", "VRT", "NVO", "SPGI"} <= set(insts)
    assert insts["EURUSD=X"]["positioning"]["market"] == "EURO FX"
    assert insts["EURUSD=X"]["positioning"].get("report", "tff") == "tff"   # financial, unchanged
    assert "positioning" not in insts["GC=F"]


# --- COT report routing ---------------------------------------------
def test_disaggregated_parse_uses_managed_money_fields():
    rows = [{"report_date_as_yyyy_mm_dd": "2026-06-23",
             "m_money_positions_long_all": "5000", "m_money_positions_short_all": "3000",
             "open_interest_all": "20000"}]
    p = _parse_rows(rows, REPORTS["disaggregated"]["long"], REPORTS["disaggregated"]["short"])
    assert p[0].net == 2000.0
    assert REPORTS["disaggregated"]["dataset"] == "72hh-3qpy"
    assert REPORTS["tff"]["dataset"] == "gpe5-46if"


def test_fx_cot_passes_report_for_copper(monkeypatch):
    captured = {}

    class FakeProv:
        name = "fake"
        def fetch_history(self, market, *, lookback_weeks, report="tff"):
            captured["market"] = market
            captured["report"] = report
            return [CotReport(report_date=date(2026, 6, 23), long=5000, short=3000,
                              net=2000, open_interest=20000, source="fake")]

    import app.providers.positioning as pos
    monkeypatch.setattr(pos, "build_positioning_provider", lambda name: FakeProv())
    inst = {"positioning": {"provider": "cftc", "report": "disaggregated",
                            "market": "COPPER- #1", "lookback_weeks": 156}}
    res = board._fx_cot(inst, {})
    assert captured["report"] == "disaggregated" and captured["market"] == "COPPER- #1"
    assert res["net"] == 2000 and res["state"] in ("crowded_long", "crowded_short", "neutral")


def test_fx_cot_defaults_to_tff(monkeypatch):
    captured = {}

    class FakeProv:
        name = "fake"
        def fetch_history(self, market, *, lookback_weeks, report="tff"):
            captured["report"] = report
            return [CotReport(report_date=date(2026, 6, 23), long=1, short=1, net=0,
                              open_interest=1, source="fake")]

    import app.providers.positioning as pos
    monkeypatch.setattr(pos, "build_positioning_provider", lambda name: FakeProv())
    board._fx_cot({"positioning": {"market": "EURO FX"}}, {})
    assert captured["report"] == "tff"   # financial instruments unchanged

"""EUR/USD decision board: derived Fed-ECB spread, config, RSI thresholds, assembly.

FRED and yfinance are mocked — no real calls.
"""
from datetime import date, timedelta

from pytest import approx

from app.config import load_config
from app.ingestion.macro_job import _compute_derived, run_macro_ingestion
from app.providers.macro.base import MacroObservation
from app.technicals import compute_technicals, rsi_zone


# --- config ----------------------------------------------------------
def _eurusd_cfg():
    cfg = load_config()
    inst = next(i for i in cfg.decision_board["instruments"] if i["symbol"] == "EURUSD=X")
    return cfg, inst


def test_eurusd_config_loaded():
    cfg, inst = _eurusd_cfg()
    assert inst["options_proxy"] == "FXE"
    assert inst["rsi"]["overbought"] == 70 and inst["rsi"]["oversold"] == 30   # standard, not 80/40
    drivers = {d["id"]: d for d in inst["macro_drivers"]}
    main = drivers["FED_ECB_SPREAD"]
    assert main["supportive_when"] == "falling" and main["weight"] == 1.5      # principal driver
    # Derived spec declared.
    derived = {d["id"]: d for d in cfg.decision_board["macro"]["derived"]}
    assert derived["FED_ECB_SPREAD"]["left"] == "DFEDTARU"
    assert derived["FED_ECB_SPREAD"]["right"] == "ECBDFR"


def test_rsi_thresholds_are_per_instrument():
    # EUR/USD uses 70/30: an RSI of 72 is "overbought" here (would be neutral for gold's 80/40).
    assert rsi_zone(72, overbought=70, oversold=30) == "overbought"
    assert rsi_zone(72, overbought=80, oversold=40) == "neutral"


# --- derived series --------------------------------------------------
def _obs(series, pairs):
    return [MacroObservation(series_id=series, obs_date=d, value=v, source="fred") for d, v in pairs]


def test_compute_derived_spread_subtracts():
    d0 = date(2026, 1, 1)
    cache = {
        "DFEDTARU": _obs("DFEDTARU", [(d0, 5.5), (d0 + timedelta(days=1), 5.5)]),
        "ECBDFR": _obs("ECBDFR", [(d0, 4.0), (d0 + timedelta(days=1), 3.75)]),
    }
    spec = {"id": "FED_ECB_SPREAD", "op": "subtract", "left": "DFEDTARU", "right": "ECBDFR"}
    rows = _compute_derived(spec, cache)
    by = {r["obs_date"]: r["value"] for r in rows}
    assert by[d0.isoformat()] == approx(1.5)                       # 5.5 - 4.0
    assert by[(d0 + timedelta(days=1)).isoformat()] == approx(1.75)  # 5.5 - 3.75
    assert all(r["series_id"] == "FED_ECB_SPREAD" for r in rows)


def test_compute_derived_carry_forward_alignment():
    # ECB rate only reported on day 1; carried forward to day 3 where Fed updates.
    d = [date(2026, 1, i) for i in range(1, 4)]
    cache = {
        "DFEDTARU": _obs("DFEDTARU", [(d[0], 5.5), (d[2], 5.25)]),
        "ECBDFR": _obs("ECBDFR", [(d[0], 4.0)]),
    }
    rows = _compute_derived({"id": "S", "op": "subtract", "left": "DFEDTARU", "right": "ECBDFR"}, cache)
    by = {r["obs_date"]: r["value"] for r in rows}
    assert by[d[0].isoformat()] == approx(1.5)
    assert by[d[2].isoformat()] == approx(1.25)   # 5.25 - 4.0 (ECB carried forward)


def test_compute_derived_no_overlap_returns_empty():
    assert _compute_derived({"id": "S", "left": "A", "right": "B"}, {"A": [], "B": []}) == []


# --- macro job computes & stores derived -----------------------------
class FakeMacroProvider:
    name = "fake"

    def __init__(self):
        d0 = date(2026, 1, 1)
        self.data = {
            "DFEDTARU": _obs("DFEDTARU", [(d0, 5.5)]),
            "ECBDFR": _obs("ECBDFR", [(d0, 4.0)]),
            "DGS2": _obs("DGS2", [(d0, 4.2)]),
            "DFII10": _obs("DFII10", [(d0, 2.1)]),
            "DTWEXBGS": _obs("DTWEXBGS", [(d0, 120.0)]),
            "T10YIE": _obs("T10YIE", [(d0, 2.3)]),
        }
        self.fetched = []

    def fetch_series(self, sid, *, days):
        self.fetched.append(sid)
        return self.data.get(sid, [])


class FakeStore:
    def __init__(self):
        self.upserts = []

    def upsert_macro_series(self, rows):
        self.upserts.extend(rows)


def test_run_macro_ingestion_stores_derived_spread():
    cfg = load_config()
    prov = FakeMacroProvider()
    store = FakeStore()
    res = run_macro_ingestion(cfg, store, prov)
    assert res["failed"] == 0
    # Components were fetched but the derived series is what gets stored under its id.
    assert "DFEDTARU" in prov.fetched and "ECBDFR" in prov.fetched
    spreads = [r for r in store.upserts if r["series_id"] == "FED_ECB_SPREAD"]
    assert spreads and spreads[0]["value"] == approx(1.5)
    # Direct drivers still stored; the raw components are NOT (only the derived).
    stored_ids = {r["series_id"] for r in store.upserts}
    assert "DGS2" in stored_ids and "DTWEXBGS" in stored_ids
    assert "DFEDTARU" not in stored_ids and "ECBDFR" not in stored_ids

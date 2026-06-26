"""Tests for the decision board: implied probabilities + assembly.

FRED and yfinance are NEVER called here — the options provider and storage are
in-memory fakes, so the math and wiring are tested in isolation.
"""
from datetime import date, timedelta

import pytest

from app import options as opt
from app.config import load_config
from app.decision.board import build_confluence, run_decision_board
from app.decision.implied import implied_probabilities
from app.providers.options.base import OptionQuote

TODAY = date(2026, 6, 25)
SIGMA = 0.20
RFR = 0.04
SPOT = 100.0


class FakeOptionsProvider:
    """Returns a single-strike ATM chain whose mid prices are generated from a
    known sigma, so the IV solver should recover SIGMA exactly."""

    name = "fake"

    def __init__(self, today=TODAY, sigma=SIGMA, r=RFR, spot=SPOT):
        self.today, self.sigma, self.r, self.spot = today, sigma, r, spot
        self.expiries = [(today + timedelta(days=d)).isoformat() for d in (1, 3, 30)]

    def get_spot(self, underlying):
        return self.spot

    def list_expiries(self, underlying):
        return list(self.expiries)

    def fetch_chain(self, underlying, expiry):
        dte = (date.fromisoformat(expiry) - self.today).days
        T = dte / 365.0
        out = []
        for ot in ("call", "put"):
            mid = opt.bs_price(ot, self.spot, self.spot, T, self.r, self.sigma)
            out.append(OptionQuote(option_type=ot, strike=self.spot,
                                   bid=mid - 0.01, ask=mid + 0.01, last=mid,
                                   volume=10, open_interest=10))
        return out


def test_implied_probabilities_recovers_iv_and_bounds():
    prov = FakeOptionsProvider()
    res = implied_probabilities(
        prov, "GLD", today=TODAY, horizons_days=[1, 3, 30], r=RFR
    )
    assert res["spot"] == SPOT
    assert len(res["horizons"]) == 3
    for h in res["horizons"]:
        assert h["available"] is True
        assert h["atm_iv"] == pytest.approx(SIGMA, abs=1e-3)   # IV recovered
        assert 0.0 < h["prob_up"] < 1.0                        # a probability
        assert h["expected_move_pct"] > 0
    # Longer horizon -> larger expected move.
    moves = [h["expected_move_pct"] for h in res["horizons"]]
    assert moves[0] < moves[-1]


def test_implied_probabilities_no_options_degrades():
    class NoOpts(FakeOptionsProvider):
        def list_expiries(self, underlying):
            return []
    res = implied_probabilities(NoOpts(), "EURUSD=X", today=TODAY,
                                horizons_days=[1], r=RFR)
    assert res["horizons"] == [] and "Nessuna catena" in res["note"]


# --- assembly --------------------------------------------------------
class FakeStorage:
    def __init__(self):
        # 60 rising closes for GC=F (newest-first as the real storage returns).
        closes = [float(100 + i) for i in range(60)]
        rows = [{"ts": f"2026-{(i % 12) + 1:02d}-01", "open": c, "high": c + 1,
                 "low": c - 1, "close": c} for i, c in enumerate(closes)]
        self._gold = list(reversed(rows))  # newest-first
        self._vix = [{"ts": "2026-06-25", "open": 18, "high": 19, "low": 17, "close": 18.0},
                     {"ts": "2026-06-24", "open": 17, "high": 18, "low": 16, "close": 17.0}]
        self.saved = {}

    def get_instrument_id(self, symbol):
        return {"GC=F": "gid", "^VIX": "vid"}.get(symbol)

    def get_price_history(self, instrument_id, limit):
        if instrument_id == "gid":
            return self._gold[:limit]
        if instrument_id == "vid":
            return self._vix[:limit]
        return []

    def get_macro_series(self, series_id, limit):
        # Newest-first: latest then previous, so direction is derivable.
        table = {
            "DFII10": [{"value": 2.10, "obs_date": "2026-06-24"}, {"value": 2.00, "obs_date": "2026-06-23"}],
            "T10YIE": [{"value": 2.30, "obs_date": "2026-06-24"}, {"value": 2.35, "obs_date": "2026-06-23"}],
            "DTWEXBGS": [{"value": 120.0, "obs_date": "2026-06-24"}, {"value": 121.0, "obs_date": "2026-06-23"}],
        }
        return table.get(series_id, [])[:limit]

    def list_upcoming_events(self, limit):
        return [{"title": "FOMC rate decision", "event_time": "2026-07-29", "importance": "high"},
                {"title": "Some earnings", "event_time": "2026-07-01", "importance": "low"}]

    def list_statements_by_figure(self, figure, limit):
        return [{"figure": figure, "statement": "Rates to stay restrictive.",
                 "stated_at": "2026-06-20"}]

    def upsert_decision_board(self, symbol, board):
        self.saved[symbol] = board


def test_run_decision_board_assembles_and_saves():
    cfg = load_config()
    storage = FakeStorage()
    prov = FakeOptionsProvider()
    res = run_decision_board(cfg, storage, prov, ai=None)
    assert res["ok"] == 1 and res["failed"] == 0

    board = storage.saved["GC=F"]
    # Macro drivers resolved with direction + context state.
    drivers = {d["id"]: d for d in board["macro_drivers"]}
    assert drivers["DFII10"]["direction"] == "up"        # 2.00 -> 2.10
    assert drivers["DFII10"]["state"] == "headwind"      # rising real rate = headwind for gold
    assert drivers["T10YIE"]["direction"] == "down"      # 2.35 -> 2.30
    assert drivers["DTWEXBGS"]["state"] == "tailwind"    # dollar falling = tailwind
    assert drivers["^VIX"]["value"] == 18.0 and drivers["^VIX"]["direction"] == "up"

    # Honest base rate present with its sample size + caveat.
    assert "sample_size" in board["base_rate"]
    assert "rimbalzo" in board["base_rate"]["caveat"].lower()

    # Implied probabilities (market odds) for 3 horizons.
    assert len(board["implied"]["horizons"]) == 3

    # Confluence rows exist and only use descriptive states (no buy/sell).
    states = {r["state"] for r in board["confluence"]}
    assert states <= {"tailwind", "headwind", "watch", "neutral"}

    # Powell statement and the FOMC event were picked up.
    assert board["figures"] and board["figures"][0]["figure"] == "Jerome Powell"
    assert any("FOMC" in e["title"] for e in board["events"])


def test_build_confluence_states_are_descriptive_only():
    drivers = [{"id": "DFII10", "label": "Tasso reale 10y", "value": 2.1,
                "direction": "up", "state": "headwind", "interpretation": "x"}]
    tech = {"streak": {"direction": "down", "length": 6}, "ma": [], "rsi": {},
            "range": {}, "atr": None}
    rows = build_confluence(drivers, tech, {"status": "ok"}, None)
    streak_row = next(r for r in rows if r["key"] == "streak")
    assert streak_row["state"] == "watch"     # long streak -> attention, not a call

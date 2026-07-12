"""Tests for the local control API (/refresh free, /decision/{sym}/ai paid).

The worker jobs and the AI client are monkeypatched — NO external calls. We
verify: token auth, that /refresh makes NO AI call, the concurrency/rate guards,
and the server-side level-probability math.
"""
import threading

import pytest
from fastapi.testclient import TestClient

import app.api as api
from app.config import load_config

TOKEN = "secret-test"
HDR = {"X-API-Token": TOKEN}


class FakeStorage:
    def __init__(self, board=None):
        self._board = board
        self.saved = {}

    def get_decision_board(self, symbol):
        return self._board

    def upsert_decision_board(self, symbol, board):
        self.saved[symbol] = board


def _no_ai():
    raise AssertionError("build_ai_client must NOT be called by /refresh")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("API_TOKEN", TOKEN)
    # Stub every worker job + provider builder so /refresh does real flow, no I/O.
    for name in ("run_prices_ingestion", "run_macro_ingestion",
                 "run_calendar_ingestion", "run_decision_board", "run_event_experiment"):
        monkeypatch.setattr(api, name, lambda *a, **k: {"ok": 1, "failed": 0})
    monkeypatch.setattr(api, "seed_universe_and_holdings", lambda *a, **k: None)
    for name in ("build_price_provider", "build_macro_provider",
                 "build_calendar_provider", "build_options_provider"):
        monkeypatch.setattr(api, name, lambda *a, **k: object())
    monkeypatch.setattr(api, "build_ai_client", _no_ai)
    api._state["cfg"] = load_config()
    api._state["storage"] = FakeStorage()
    api._ai_last_run.clear()
    yield TestClient(api.app)
    api._state.clear()
    api._ai_last_run.clear()


# --- auth ------------------------------------------------------------
def test_refresh_requires_token(client):
    assert client.post("/refresh").status_code == 401


def test_refresh_503_without_server_token(client, monkeypatch):
    monkeypatch.delenv("API_TOKEN", raising=False)
    assert client.post("/refresh", headers=HDR).status_code == 503


# --- /refresh is FREE (no AI) ----------------------------------------
def test_refresh_runs_jobs_and_never_calls_ai(client):
    res = client.post("/refresh", headers=HDR)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True and body["ai_called"] is False
    assert "prices" in body["steps"] and "decision_board" in body["steps"]
    # _no_ai would have raised if /refresh touched the AI client.


def test_refresh_concurrency_guard(client):
    api._refresh_lock.acquire()
    try:
        assert client.post("/refresh", headers=HDR).status_code == 409
    finally:
        api._refresh_lock.release()


# --- /decision/{sym}/ai is PAID --------------------------------------
def _board_with_implied():
    return {
        "symbol": "GC=F", "name": "Gold", "last": 3000.0,
        "implied": {"spot": 3000.0, "risk_free_rate": 0.04, "horizons": [
            {"available": True, "target_days": 30, "expiry": "2026-07-29",
             "days_to_expiry": 33, "atm_iv": 0.18},
        ]},
    }


def test_ai_requires_token(client):
    assert client.post("/decision/GC=F/ai").status_code == 401


def test_ai_404_without_snapshot(client):
    assert client.post("/decision/GC=F/ai", headers=HDR, json={}).status_code == 404


def test_ai_runs_and_saves(client, monkeypatch):
    api._state["storage"] = FakeStorage(board=_board_with_implied())
    monkeypatch.setattr(api, "build_ai_client", lambda: object())
    monkeypatch.setattr(api, "summarize_decision_board",
                        lambda *a, **k: {"read": "ok", "conviction": "bassa"})
    res = client.post("/decision/GC=F/ai", headers=HDR, json={"level": 3100})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True and body["ai_summary"]["read"] == "ok"
    # Level probabilities were computed server-side and saved.
    assert body["level_probs"]["level"] == 3100
    assert "GC=F" in api._state["storage"].saved


def test_ai_concurrency_guard(client):
    api._state["storage"] = FakeStorage(board=_board_with_implied())
    lock = api._ai_lock("GC=F")
    lock.acquire()
    try:
        assert client.post("/decision/GC=F/ai", headers=HDR, json={}).status_code == 409
    finally:
        lock.release()


def test_ai_rate_limit_guard(client, monkeypatch):
    api._state["storage"] = FakeStorage(board=_board_with_implied())
    import time
    api._ai_last_run["GC=F"] = time.monotonic()   # just ran
    assert client.post("/decision/GC=F/ai", headers=HDR, json={}).status_code == 429


# --- server-side level probabilities ---------------------------------
def test_level_probs_above_below_sum_to_one():
    board = _board_with_implied()
    out = api._level_probs(board, 3100.0)
    h = out["horizons"][0]
    assert h["prob_above"] is not None
    assert h["prob_above"] + h["prob_below"] == pytest.approx(1.0, abs=1e-9)
    # K above spot -> prob_above must be < 0.5.
    assert h["prob_above"] < 0.5


def test_level_probs_below_spot_is_more_likely_above():
    board = _board_with_implied()
    out = api._level_probs(board, 2900.0)   # K below spot
    assert out["horizons"][0]["prob_above"] > 0.5

"""Light test for price ingestion: per-symbol isolation + storage writes.

Uses an in-memory fake storage and fake providers — no network, no DB.
"""
from datetime import datetime, timezone

from app.config import AppConfig, Instrument
from app.ingestion.prices_job import run_prices_ingestion
from app.providers.prices.base import PriceBar


class FakeStorage:
    def __init__(self):
        self.prices = []
        self.ids = {"AAA": "id-aaa", "BBB": "id-bbb"}

    def get_instrument_id(self, symbol):
        return self.ids.get(symbol)

    def upsert_prices(self, rows):
        self.prices.extend(rows)


class FakeProvider:
    name = "fake"

    def __init__(self, fail_for=()):
        self.fail_for = set(fail_for)

    def fetch_history(self, symbol, days):
        if symbol in self.fail_for:
            raise RuntimeError(f"boom {symbol}")
        return [
            PriceBar(
                symbol=symbol,
                ts=datetime(2026, 1, 2, tzinfo=timezone.utc),
                open=1.0, high=2.0, low=0.5, close=1.5, volume=1000,
                source=self.name,
            )
        ]


def _cfg():
    return AppConfig(
        base_currency="USD",
        account={"size": 1000},
        risk={},
        universe=[Instrument(symbol="AAA"), Instrument(symbol="BBB")],
        holdings=[],
        schedule={},
        providers={"prices": "fake"},
        indicators={"history_days": 10},
    )


def test_prices_ingestion_writes_rows():
    storage = FakeStorage()
    res = run_prices_ingestion(_cfg(), storage, FakeProvider())
    assert res == {"ok": 2, "failed": 0}
    assert len(storage.prices) == 2
    assert storage.prices[0]["instrument_id"] in {"id-aaa", "id-bbb"}
    assert storage.prices[0]["close"] == 1.5


def test_prices_ingestion_isolates_failures():
    storage = FakeStorage()
    # BBB fails (after retries); AAA still succeeds.
    res = run_prices_ingestion(_cfg(), storage, FakeProvider(fail_for={"BBB"}))
    assert res == {"ok": 1, "failed": 1}
    assert len(storage.prices) == 1

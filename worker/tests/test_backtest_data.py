"""Data loader — caching behaviour with a mocked provider (no network)."""
from datetime import datetime, timedelta, timezone

from app.backtest.data import load_history
from app.providers.prices.base import PriceBar


class FakeProvider:
    name = "fake"

    def __init__(self, n=12):
        self.calls = 0
        self.n = n

    def fetch_history(self, symbol, days):
        self.calls += 1
        base = datetime(2020, 1, 1, tzinfo=timezone.utc)
        bars = []
        for i in range(self.n):
            px = 100.0 + i
            bars.append(PriceBar(symbol=symbol, ts=base + timedelta(days=i),
                                 open=px, high=px + 1, low=px - 1, close=px + 0.5,
                                 volume=1000, source="fake"))
        return bars


def test_load_history_fetches_then_caches(tmp_path):
    prov = FakeProvider(n=10)
    df1 = load_history("GC=F", prov, days=100, cache_dir=tmp_path)
    assert len(df1) == 10 and prov.calls == 1
    assert list(df1.columns) == ["open", "high", "low", "close", "volume"]

    # Second call within TTL -> served from cache, provider NOT hit again.
    df2 = load_history("GC=F", prov, days=100, cache_dir=tmp_path)
    assert prov.calls == 1 and len(df2) == 10


def test_force_refetches(tmp_path):
    prov = FakeProvider(n=8)
    load_history("X", prov, days=100, cache_dir=tmp_path)
    load_history("X", prov, days=100, cache_dir=tmp_path, force=True)
    assert prov.calls == 2


def test_stale_cache_used_when_fetch_fails(tmp_path):
    prov = FakeProvider(n=6)
    load_history("Y", prov, days=100, cache_dir=tmp_path)  # writes cache

    class Boom(FakeProvider):
        def fetch_history(self, symbol, days):
            raise RuntimeError("provider down")

    df = load_history("Y", Boom(), days=100, cache_dir=tmp_path, force=True)
    assert len(df) == 6   # fell back to the stale cache instead of crashing

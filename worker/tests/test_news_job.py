"""Light test for news ingestion: provider isolation + url/title dedup."""
from datetime import datetime, timezone

from app.config import AppConfig
from app.ingestion.news_job import run_news_ingestion
from app.providers.news.base import NewsItem


class FakeStorage:
    def __init__(self):
        self.rows = []

    def upsert_news_items(self, rows):
        self.rows.extend(rows)


class FakeProvider:
    def __init__(self, name, items=(), fail=False):
        self.name = name
        self._items = list(items)
        self._fail = fail

    def fetch(self, keywords):
        if self._fail:
            raise RuntimeError(f"{self.name} down")
        return self._items


def _item(title, url):
    return NewsItem(
        title=title, url=url, source="src",
        published_at=datetime(2026, 6, 20, tzinfo=timezone.utc), summary=None,
    )


def _cfg():
    return AppConfig(
        base_currency="USD", account={}, risk={}, universe=[], holdings=[],
        schedule={}, providers={}, indicators={},
        news={"keywords": ["Fed"]},
    )


def test_news_dedup_by_url_and_title():
    p1 = FakeProvider("a", [_item("Fed holds", "http://x/1"), _item("Gold up", "http://x/2")])
    p2 = FakeProvider("b", [
        _item("Fed holds", "http://x/3"),     # dup title, diff url -> dropped
        _item("ECB meets", "http://x/2"),      # dup url, diff title -> dropped
        _item("New thing", "http://x/4"),      # kept
    ])
    storage = FakeStorage()
    res = run_news_ingestion(_cfg(), storage, [p1, p2])
    titles = sorted(r["title"] for r in storage.rows)
    assert titles == ["Fed holds", "Gold up", "New thing"]
    assert res == {"ok": 3, "failed": 0}


def test_news_provider_failure_isolated():
    good = FakeProvider("good", [_item("Fed holds", "http://x/1")])
    bad = FakeProvider("bad", fail=True)
    storage = FakeStorage()
    res = run_news_ingestion(_cfg(), storage, [bad, good])
    assert len(storage.rows) == 1
    assert res["ok"] == 1 and res["failed"] == 1

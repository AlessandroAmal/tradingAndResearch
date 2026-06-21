"""Light test for key-figure ingestion: per-figure isolation + dedup."""
from datetime import datetime, timezone

from app.config import AppConfig
from app.ingestion.figures_job import run_figures_ingestion
from app.providers.figures.base import FigureStatement


class FakeStorage:
    def __init__(self):
        self.rows = []

    def upsert_figure_statements(self, rows):
        self.rows.extend(rows)


class FakeSource:
    """Returns canned statements per figure (keyed by name); can fail one."""

    name = "fake"

    def __init__(self, by_name, fail_for=()):
        self._by_name = by_name
        self._fail = set(fail_for)

    def fetch(self, figure):
        name = figure["name"]
        if name in self._fail:
            raise RuntimeError(f"{name} source down")
        return self._by_name.get(name, [])


def _stmt(figure, text, url):
    return FigureStatement(
        figure=figure, text=text, source="src", url=url,
        stated_at=datetime(2026, 6, 21, tzinfo=timezone.utc), role="r",
    )


def _cfg(figures):
    return AppConfig(
        base_currency="USD", account={}, risk={}, universe=[], holdings=[],
        schedule={}, providers={}, indicators={}, figures=figures,
    )


def test_figures_dedup_by_url_and_text():
    src = FakeSource({
        # same text twice -> the text dup is dropped
        "Powell": [_stmt("Powell", "Powell speaks", "http://x/1"),
                   _stmt("Powell", "Powell speaks", "http://x/9")],
        # same url twice -> the url dup is dropped
        "Musk": [_stmt("Musk", "Musk tweets", "http://x/2"),
                 _stmt("Musk", "Tesla news", "http://x/2")],
    })
    storage = FakeStorage()
    res = run_figures_ingestion(
        _cfg([{"name": "Powell"}, {"name": "Musk"}]), storage, src
    )
    texts = sorted(r["statement"] for r in storage.rows)
    assert texts == ["Musk tweets", "Powell speaks"]
    # canonical column is `statement`, not `headline`/`text`
    assert "statement" in storage.rows[0] and "text" not in storage.rows[0]
    assert res == {"ok": 2, "failed": 0}


def test_figures_source_failure_isolated():
    src = FakeSource(
        {"Powell": [_stmt("Powell", "Powell speaks", "http://x/1")]},
        fail_for={"Musk"},
    )
    storage = FakeStorage()
    res = run_figures_ingestion(
        _cfg([{"name": "Powell"}, {"name": "Musk"}]), storage, src
    )
    assert len(storage.rows) == 1
    assert res["ok"] == 1 and res["failed"] == 1

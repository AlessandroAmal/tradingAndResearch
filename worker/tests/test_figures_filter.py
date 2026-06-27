"""Tests for the tightened key-figure sourcing filter.

The figure's NAME must appear in the title (so institution news / obituaries /
other officials stop landing under a person), and obvious non-statements are
dropped. Feed parsing is monkeypatched — no network.
"""
from app.providers.figures import news_source
from app.providers.figures.news_source import NewsFigureSource, _match_terms


def _entry(title, link="http://x/1"):
    return {"title": title, "link": link, "published_parsed": None,
            "source": {"title": "Test"}}


FAKE_ENTRIES = [
    _entry("Powell says rates will stay restrictive for now", "http://x/a"),
    _entry("Alan Greenspan, former Fed chair, dies at 99", "http://x/b"),  # obituary, no Powell
    _entry("NY Fed's Marchioni on money market operations", "http://x/c"),  # other official
    _entry("Federal Reserve releases bank stress test results", "http://x/d"),  # institution
]


def test_match_terms_default_includes_surname():
    assert _match_terms({"name": "Jerome Powell"}) == ["Jerome Powell", "Powell"]
    assert _match_terms({"name": "X", "match_terms": ["PBoC"]}) == ["PBoC"]


def test_only_real_statements_kept(monkeypatch):
    monkeypatch.setattr(news_source, "_safe_parse", lambda url, label: FAKE_ENTRIES)
    src = NewsFigureSource()
    out = src.fetch({"name": "Jerome Powell", "match_terms": ["Powell"], "keywords": ["Powell"]})
    titles = [s.text for s in out]
    assert any("Powell says" in t for t in titles)        # the real statement kept
    assert not any("Greenspan" in t for t in titles)       # obituary dropped (no name + drop term)
    assert not any("Marchioni" in t for t in titles)       # other official dropped (no Powell)
    assert not any("stress test" in t for t in titles)     # institution news dropped (no Powell)
    assert len(out) == 1


def test_keep_rules_directly():
    src = NewsFigureSource()
    assert src._keep("Powell signals patience on cuts", ["Powell"]) is True
    assert src._keep("Fed official speaks", ["Powell"]) is False      # name missing
    assert src._keep("Powell dies — obituary", ["Powell"]) is False   # drop term


def test_require_name_can_be_disabled():
    src = NewsFigureSource(filter_cfg={"require_name_in_title": False, "drop_terms": []})
    assert src._keep("Fed official speaks", ["Powell"]) is True

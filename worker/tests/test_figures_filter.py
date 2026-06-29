"""Tests for the tightened key-figure sourcing filter.

A surname-only match (e.g. "Powell") is kept only with DOMAIN context (Fed/rates),
killing homonyms (Lucy/Daryl Powell, St Helens rugby). A full distinctive name
always passes. Obvious non-statements are dropped. No network (parsing mocked).
"""
from app.providers.figures import news_source
from app.providers.figures.news_source import NewsFigureSource, _match_terms

POWELL = ["Jerome Powell", "Powell"]
CTX = ["fed", "fomc", "rate", "rates", "inflation"]


def _entry(title, link="http://x/1"):
    return {"title": title, "link": link, "published_parsed": None, "source": {"title": "Test"}}


def test_match_terms_default_includes_surname():
    assert _match_terms({"name": "Jerome Powell"}) == ["Jerome Powell", "Powell"]
    assert _match_terms({"name": "X", "match_terms": ["PBoC"]}) == ["PBoC"]


def test_full_name_always_passes():
    src = NewsFigureSource()
    assert src._keep("Jerome Powell: rates to stay restrictive", POWELL, []) is True


def test_surname_needs_domain_context():
    src = NewsFigureSource()
    # surname + Fed context -> keep
    assert src._keep("Powell signals Fed patience on rates", POWELL, CTX) is True
    # surname WITHOUT context -> drop (homonyms)
    assert src._keep("Lucy Powell to lead the UK Commons", POWELL, CTX) is False


def test_homonyms_and_obituaries_dropped(monkeypatch):
    entries = [
        _entry("Jerome Powell says rates stay restrictive", "http://x/a"),     # keep (full name)
        _entry("Powell warns on inflation risks", "http://x/b"),               # keep (surname+ctx)
        _entry("Daryl Powell named St Helens rugby coach", "http://x/c"),      # drop (rugby/st helens)
        _entry("Lucy Powell in UK Commons reshuffle", "http://x/d"),           # drop (no Fed context)
        _entry("Alan Greenspan dies at 99", "http://x/e"),                     # drop (obituary)
    ]
    monkeypatch.setattr(news_source, "_safe_parse", lambda url, label: entries)
    src = NewsFigureSource(filter_cfg={
        "drop_terms": ["rugby", "st helens", "dies"],
        "context_terms": CTX,
    })
    out = src.fetch({"name": "Jerome Powell", "match_terms": POWELL, "keywords": ["Powell"]})
    titles = [s.text for s in out]
    assert any("Jerome Powell says" in t for t in titles)
    assert any("Powell warns on inflation" in t for t in titles)
    assert not any("rugby" in t.lower() for t in titles)
    assert not any("Commons" in t for t in titles)
    assert not any("Greenspan" in t for t in titles)
    assert len(out) == 2


def test_require_name_can_be_disabled():
    src = NewsFigureSource(filter_cfg={"require_name_in_title": False, "drop_terms": []})
    assert src._keep("Fed official speaks", ["Powell"], []) is True


def test_institution_single_word_without_context_still_matches():
    # An institution figure (no domain context configured) keeps a bare match.
    src = NewsFigureSource()
    assert src._keep("PBoC cuts reserve requirement", ["PBoC"], []) is True

"""Thematic concentration — apparent diversification that is not real."""
from pytest import approx

from app.concentration import theme_concentration, THEME_LABELS


THEMES = {"MSFT": ["ai_datacenter"], "AVGO": ["ai_datacenter", "semis"],
          "VRT": ["ai_datacenter"], "NVO": ["pharma"], "SPGI": ["financials"]}


def test_ai_theme_flagged_across_names():
    positions = [
        {"symbol": "MSFT", "notional": 40_000},
        {"symbol": "AVGO", "notional": 30_000},
        {"symbol": "VRT", "notional": 20_000},
        {"symbol": "NVO", "notional": 10_000},
    ]
    out = theme_concentration(positions, THEMES)
    ai = next(t for t in out if t["theme"] == "ai_datacenter")
    assert ai["positions"] == 3 and ai["concentrated"] is True
    assert ai["symbols"] == ["AVGO", "MSFT", "VRT"]
    assert ai["weight"] == approx(90_000 / 100_000)          # 90% of the book
    assert ai["label"] == THEME_LABELS["ai_datacenter"]
    # a single-name theme is NOT flagged as concentration
    pharma = next(t for t in out if t["theme"] == "pharma")
    assert pharma["positions"] == 1 and pharma["concentrated"] is False
    # flagged themes sort first
    assert out[0]["theme"] == "ai_datacenter"


def test_no_positions_no_themes():
    assert theme_concentration([], THEMES) == []


def test_weight_none_when_zero_notional():
    out = theme_concentration([{"symbol": "MSFT", "notional": 0}, {"symbol": "VRT", "notional": 0}], THEMES)
    ai = next(t for t in out if t["theme"] == "ai_datacenter")
    assert ai["weight"] is None and ai["positions"] == 2 and ai["concentrated"] is True


def test_untagged_symbol_ignored():
    out = theme_concentration([{"symbol": "XYZ", "notional": 5000}], {"XYZ": []})
    assert out == []

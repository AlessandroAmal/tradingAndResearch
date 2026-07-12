"""Single-stock template (NVDA/TSLA/GOOGL): proxy = the stock, COT off, earnings.

External sources (yfinance) mocked. Gold/EUR-USD/Nasdaq must stay unchanged.
"""
from datetime import date

import app.decision.board as board
from app.config import load_config
from app.decision.synthesis import confluence_read
from app.ingestion import earnings as earn


def _insts():
    cfg = load_config()
    return {i["symbol"]: i for i in cfg.decision_board["instruments"]}


# --- config: the three stocks share the single-stock template --------
def test_single_stock_config_template():
    insts = _insts()
    for sym in ("NVDA", "TSLA", "GOOGL"):
        i = insts[sym]
        assert i["options_proxy"] == sym          # proxy = the stock itself, no ETF
        assert "positioning" not in i             # COT OFF (no COT on single names)
        assert i.get("earnings") is True
        drivers = {d["id"] for d in i["macro_drivers"]}
        assert drivers == {"DFII10", "^VIX"}      # only background macro context
        assert all(d["weight"] <= 0.3 for d in i["macro_drivers"])   # low weight
        assert "cot" not in i["synthesis"]["weights"]   # no COT factor weight
    assert insts["NVDA"]["figures"] == ["Jensen Huang"]
    assert insts["TSLA"]["figures"] == ["Elon Musk"]
    assert insts["GOOGL"]["figures"] == ["Sundar Pichai"]
    # GOOGL less volatile -> standard RSI; NVDA/TSLA wider band.
    assert insts["GOOGL"]["rsi"]["overbought"] == 70
    assert insts["NVDA"]["rsi"]["overbought"] == 75


def test_other_instruments_unchanged():
    insts = _insts()
    assert "fx_signals" not in insts["GC=F"] and "positioning" not in insts["GC=F"]
    assert insts["EURUSD=X"]["positioning"]["market"] == "EURO FX"
    assert insts["^NDX"]["positioning"]["market"] == "NASDAQ MINI"


def test_fundamentals_only_on_single_stocks():
    insts = _insts()
    for sym in ("NVDA", "TSLA", "GOOGL"):
        assert insts[sym].get("fundamentals") is True
    # Company fundamentals do NOT apply to indices / FX / commodities.
    for sym in ("GC=F", "EURUSD=X", "^NDX", "HG=F", "^GDAXI"):
        assert not insts[sym].get("fundamentals")


# --- COT absent is handled, not crashing -----------------------------
def test_cot_off_returns_none():
    assert board._fx_cot({}, {}) is None                       # no positioning block
    assert board._fx_cot({"positioning": {}}, {}) is None


def test_synthesis_without_cot_has_no_cot_factor_and_no_prob():
    fx = {"risk_reversal": [{"target_days": 30, "days_to_expiry": 30, "rr": 0.02,
                             "reliability": "ok", "percentile": 0.8}],
          "cot": None,
          "expected_move_events": [{"event": "NVDA earnings", "event_date": "2026-07-20",
                                    "expected_move_pct": 8.0}]}
    res = confluence_read(drivers=[], technicals={}, implied=None, next_event=None,
                          weights={"skew": 0.5}, fx=fx)
    keys = {f["key"] for f in res["factors"]}
    assert "skew" in keys and "cot" not in keys                # COT absent -> no factor
    assert all("prob" not in k.lower() for k in res["lean"])   # no directional probability


# --- earnings -> calendar events (symbol-scoped) ---------------------
def test_upcoming_earnings_events(monkeypatch):
    monkeypatch.setattr(earn, "earnings_dates",
                        lambda sym, limit=40: [date(2026, 5, 1), date(2026, 7, 20), date(2026, 10, 30)])
    cfg = load_config()
    evs = earn.upcoming_earnings_events(cfg, today=date(2026, 6, 28))
    by_sym = {e.symbols[0]: e for e in evs}
    assert {"NVDA", "TSLA", "GOOGL"} <= set(by_sym)
    nv = by_sym["NVDA"]
    assert nv.event_time.date() == date(2026, 7, 20)   # next future date
    assert nv.category == "earnings" and "earnings" in nv.title.lower()
    assert nv.symbols == ["NVDA"]


def test_upcoming_earnings_none_when_no_future(monkeypatch):
    monkeypatch.setattr(earn, "earnings_dates", lambda sym, limit=40: [date(2020, 1, 1)])
    assert earn.upcoming_earnings_events(load_config(), today=date(2026, 6, 28)) == []


def test_past_earnings_window(monkeypatch):
    monkeypatch.setattr(earn, "earnings_dates",
                        lambda sym, limit=40: [date(2019, 1, 1), date(2024, 2, 1), date(2026, 7, 20)])
    out = earn.past_earnings("NVDA", date(2023, 1, 1), date(2026, 6, 28))
    assert out == [date(2024, 2, 1)]   # only in [start, today)


# --- symbol-scoped event filter -------------------------------------
def test_filter_events_symbol_scoped():
    events = [
        {"title": "NVIDIA earnings", "symbols": ["NVDA"]},   # stock-specific
        {"title": "FOMC decision", "symbols": []},           # macro (keyword)
        {"title": "Tesla earnings", "symbols": ["TSLA"]},
    ]
    kws = ["NVDA", "earnings", "FOMC"]
    nv = [e["title"] for e in board._filter_events(events, kws, "NVDA", 6)]
    assert "NVIDIA earnings" in nv and "FOMC decision" in nv and "Tesla earnings" not in nv
    gg = [e["title"] for e in board._filter_events(events, ["FOMC"], "GOOGL", 6)]
    assert gg == ["FOMC decision"]   # other stocks' earnings never leak in


# =====================================================================
# Book holdings — MSFT/AVGO/VRT/NVO/SPGI reuse the single-stock template.
# =====================================================================
BOOK = ("MSFT", "AVGO", "VRT", "NVO", "SPGI")


def test_book_holdings_use_single_stock_template():
    insts = _insts()
    for sym in BOOK:
        i = insts[sym]
        assert i["options_proxy"] == sym          # proxy = the stock itself
        assert "positioning" not in i             # COT OFF on single names
        assert i.get("earnings") is True and i.get("fundamentals") is True
        drivers = {d["id"] for d in i["macro_drivers"]}
        assert drivers == {"DFII10", "^VIX"}      # macro = background only
        assert all(d["weight"] <= 0.3 for d in i["macro_drivers"])  # low weight
        assert "cot" not in i["synthesis"]["weights"]


def test_book_holdings_themes_and_notes():
    insts = _insts()
    assert insts["MSFT"]["themes"] == ["ai_datacenter"]
    assert "ai_datacenter" in insts["AVGO"]["themes"] and "semis" in insts["AVGO"]["themes"]
    assert insts["VRT"]["themes"] == ["ai_datacenter"]
    assert insts["NVO"]["themes"] == ["pharma"]
    assert insts["SPGI"]["themes"] == ["financials"]
    # idiosyncratic / defensive names carry a UI note; NVO's macro weight is tiny.
    for sym in ("VRT", "NVO", "SPGI"):
        assert insts[sym].get("board_note")
    assert all(d["weight"] <= 0.15 for d in insts["NVO"]["macro_drivers"])  # macro ~irrelevant


def test_book_holdings_in_universe_with_themes():
    from app.config import load_config
    uni = {i.symbol: i for i in load_config().universe}
    for sym in BOOK:
        assert sym in uni and uni[sym].asset_class == "equity" and uni[sym].themes


def test_dual_lenses_are_honest_no_direction():
    from app.decision.board import DUAL_LENSES
    assert {"holding", "trade", "note"} <= set(DUAL_LENSES)
    assert "FONDAMENTALI" in DUAL_LENSES["holding"] and "UTILI" in DUAL_LENSES["trade"]
    blob = " ".join(DUAL_LENSES.values()).lower()
    for word in ("comprare", "vendere", "salirà", "scenderà", "% di salita"):
        assert word not in blob                    # no directional call
    assert "previsione" in DUAL_LENSES["note"].lower()


# =====================================================================
# The 5 fixed sections — per-instrument emphasis (config override + default).
# =====================================================================
def test_section_emphasis_defaults_and_overrides():
    from app.decision.board import _section_emphasis, _SECTION_KEYS
    insts = _insts()
    # every instrument exposes all 5 sections
    for sym in ("GC=F", "NVDA", "^NDX", "HG=F", "NVO"):
        emp = _section_emphasis(insts[sym])
        assert set(emp) == set(_SECTION_KEYS)
        assert all(0 <= v <= 3 for v in emp.values())
    # stock default: fundamentals + news primary, macro background
    nv = _section_emphasis(insts["NVDA"])
    assert nv["fundamentals"] == 3 and nv["news"] == 3 and nv["macro"] == 1
    # macro instrument default: macro primary, no company fundamentals
    au = _section_emphasis(insts["GC=F"])
    assert au["macro"] == 3 and au["fundamentals"] == 0
    # config overrides: NVO macro~off + fundamentals primary; copper news primary
    nvo = _section_emphasis(insts["NVO"])
    assert nvo["macro"] == 0 and nvo["fundamentals"] == 3
    assert _section_emphasis(insts["HG=F"])["news"] == 3

"""Real-portfolio backend: ISIN/ticker resolution (success, ambiguity, failure→
manual, persisted map), holding upsert bootstrapping (instrument+prices+FX), and
the holdings↔positions separation. Fakes only — no network, no DB."""
from datetime import datetime, timezone

import pytest

from app.portfolio import (
    base_currency,
    eur_pair_for,
    resolve_symbol,
    save_holding,
)
from app.providers.lookup.base import LookupResult


class _Cfg:
    def __init__(self):
        self.raw = {"portfolio": {"base_currency": "EUR", "history_days": 300,
                                  "eur_pairs": {"USD": "EURUSD=X", "DKK": "EURDKK=X"}}}

    @property
    def portfolio(self):
        return dict(self.raw.get("portfolio", {}))


class _Bar:
    def __init__(self):
        self.ts = datetime(2026, 8, 20, tzinfo=timezone.utc)
        self.open = self.high = self.low = self.close = 100.0
        self.volume = 1.0
        self.source = "fake"


class _Provider:
    def __init__(self):
        self.fetched = []

    def fetch_history(self, symbol, days):
        self.fetched.append(symbol)
        return [_Bar()]


class _Lookup:
    """Configurable fake: `candidates` per query, `describe_map` per ticker."""
    def __init__(self, candidates=None, describe_map=None):
        self._c = candidates or {}
        self._d = describe_map or {}

    def resolve(self, query):
        return self._c.get(query, [])

    def currency_for(self, symbol):
        d = self._d.get(symbol)
        return d.currency if d else None

    def describe(self, symbol):
        return self._d.get(symbol)


class _Storage:
    """Records writes so tests can assert what was persisted, and to WHICH table."""
    def __init__(self, isin_rows=None, instruments=None):
        self._isin = list(isin_rows or [])
        self._instruments = list(instruments or [])
        self.holdings = {}
        self.positions = []          # holdings must NEVER land here
        self.upserted_instruments = []
        self.priced = []

    # isin_map
    def get_isin_map(self, isin):
        return next((r for r in self._isin if r.get("isin") == isin), None)

    def find_isin_by_ticker(self, ticker):
        return next((r for r in self._isin if str(r.get("ticker", "")).upper() == ticker.upper()), None)

    def upsert_isin_map(self, row):
        self._isin = [r for r in self._isin if r.get("ticker") != row.get("ticker")]
        self._isin.append(row)
        return row

    # instruments / prices
    def list_instruments(self):
        return self._instruments

    def upsert_instruments(self, rows):
        self.upserted_instruments.extend(rows)
        self._instruments.extend(rows)

    def get_instrument_id(self, symbol):
        return f"iid-{symbol}"

    def upsert_prices(self, rows):
        self.priced.append(rows)

    # holdings
    def upsert_holding(self, row):
        self.holdings[row["symbol"]] = row
        return row

    def delete_holding(self, symbol):
        self.holdings.pop(symbol, None)


def test_eur_pair_mapping():
    cfg = _Cfg()
    assert base_currency(cfg) == "EUR"
    assert eur_pair_for(cfg, "USD") == "EURUSD=X"
    assert eur_pair_for(cfg, "EUR") is None          # base: rate 1, no pair
    assert eur_pair_for(cfg, "SEK") is None           # unmapped: value shows n/d
    assert eur_pair_for(cfg, None) is None


def test_resolve_uses_persisted_map_first():
    st = _Storage(isin_rows=[{"isin": "US5949181045", "ticker": "MSFT",
                              "name": "Microsoft", "currency": "USD", "verified": True}])
    out = resolve_symbol(st, _Lookup(), "US5949181045")
    assert out["resolved"] and out["source"] == "isin_map"
    assert out["ticker"] == "MSFT" and out["currency"] == "USD"


def test_resolve_known_instrument_ticker():
    st = _Storage(instruments=[{"symbol": "AVGO", "name": "Broadcom", "currency": "USD"}])
    out = resolve_symbol(st, _Lookup(), "AVGO")
    assert out["resolved"] and out["source"] == "instruments" and out["currency"] == "USD"


def test_resolve_new_ticker_via_describe():
    lk = _Lookup(describe_map={"NOVO-B.CO": LookupResult(
        symbol="NOVO-B.CO", name="Novo Nordisk A/S", currency="DKK", exchange="CPH")})
    out = resolve_symbol(_Storage(), lk, "NOVO-B.CO")
    assert out["resolved"] and out["source"] == "ticker"
    assert out["currency"] == "DKK" and out["name"] == "Novo Nordisk A/S"


def test_resolve_isin_failure_asks_for_manual_ticker():
    # ISIN search returns nothing (the unreliable case) -> not resolved, no guess.
    out = resolve_symbol(_Storage(), _Lookup(candidates={}), "DK0062498333")
    assert out["is_isin"] and not out["resolved"] and out["candidates"] == []


def test_resolve_ambiguous_isin_needs_confirmation():
    lk = _Lookup(candidates={"XX0000000000": [
        LookupResult(symbol="ABC.L", name="Abc plc", exchange="LSE"),
        LookupResult(symbol="ABC.DE", name="Abc AG", exchange="XETRA")]})
    out = resolve_symbol(_Storage(), lk, "XX0000000000")
    assert out["ambiguous"] and len(out["candidates"]) == 2 and not out["resolved"]


def test_save_holding_bootstraps_and_persists():
    cfg, st, prov = _Cfg(), _Storage(), _Provider()
    res = save_holding(cfg, st, prov, _Lookup(), {
        "isin": "DK0062498333", "ticker": "NOVO-B.CO", "name": "Novo Nordisk A/S",
        "currency": "DKK", "asset_class": "equity", "quantity": 10, "avg_price": 700,
        "buy_date": "2026-01-15", "note": "core"})
    # instrument + its FX pair (EURDKK=X) both ingested
    assert "NOVO-B.CO" in prov.fetched and "EURDKK=X" in prov.fetched
    # ISIN mapping persisted and marked verified
    m = st.find_isin_by_ticker("NOVO-B.CO")
    assert m and m["isin"] == "DK0062498333" and m["verified"] is True
    # holding stored (in holdings, NOT positions) with the real fields
    h = st.holdings["NOVO-B.CO"]
    assert h["quantity"] == 10 and h["currency"] == "DKK" and h["isin"] == "DK0062498333"
    assert st.positions == []                        # holdings never touch trading positions
    assert res["bootstrap"]["fx_pair"] == "EURDKK=X"


def test_save_holding_requires_symbol():
    with pytest.raises(ValueError):
        save_holding(_Cfg(), _Storage(), _Provider(), _Lookup(), {"quantity": 1})

"""Portfolio plausibility: classify (plausibile/sospetta/non-verificabile),
historical EUR conversion, and the summary ordering. Fakes only — no network."""
from datetime import datetime, timezone

from app.portfolio_plausibility import (
    PLAUSIBLE, SUSPECT, UNVERIFIABLE, check_holdings, classify,
)


def test_classify_bands():
    assert classify(100, 105, 0.15)[0] == PLAUSIBLE          # -4.8%
    assert classify(100, 100, 0.15) == (PLAUSIBLE, 0.0)
    s, dev = classify(200, 100, 0.15)                         # +100%
    assert s == SUSPECT and dev == 1.0
    assert classify(None, 100, 0.15)[0] == UNVERIFIABLE
    assert classify(100, None, 0.15)[0] == UNVERIFIABLE
    assert classify(100, 0, 0.15)[0] == UNVERIFIABLE


class _Cfg:
    def __init__(self):
        self.raw = {"portfolio": {"base_currency": "EUR", "plausibility_threshold": 0.15,
                                  "eur_pairs": {"USD": "EURUSD=X", "HKD": "EURHKD=X"}}}

    @property
    def portfolio(self):
        return dict(self.raw["portfolio"])


class _Bar:
    def __init__(self, ts, close):
        self.ts = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
        self.close = close


class _Provider:
    def fetch_history(self, symbol, days):
        return []                                            # force stored-price path


class _Store:
    def __init__(self, holdings, prices):
        self._holdings = holdings
        self._prices = prices                                # symbol -> [{ts,close}] (any order)
        self._inst = {f"iid-{s}": {"id": f"iid-{s}", "symbol": s, "currency": "USD" if s == "MSFT" else ("HKD" if s == "1211.HK" else "EUR")}
                      for s in prices}

    def list_instruments(self):
        return list(self._inst.values())

    def list_holdings(self):
        return self._holdings

    def get_instrument_id(self, symbol):
        return f"iid-{symbol}" if symbol in self._prices else None

    def get_price_history(self, iid, limit):
        sym = iid.replace("iid-", "")
        return self._prices.get(sym, [])


def _h(**kw):
    base = {"id": "x", "symbol": "MSFT", "instrument_id": "iid-MSFT", "currency": "USD",
            "avg_price_currency": "EUR", "quantity": 1, "status": "open",
            "valuation_mode": "market", "buy_date": "2026-01-15", "avg_price": 400, "name": "MSFT"}
    base.update(kw)
    return base


def test_check_holdings_plausible_suspect_unverifiable():
    prices = {
        # MSFT close 460 USD on the buy day; EUR/USD 1.15 -> market €400 (declared €400 -> plausible)
        "MSFT": [{"ts": "2026-01-15", "close": 460.0}],
        "EURUSD=X": [{"ts": "2026-01-15", "close": 1.15}],
        # ENEL (EUR) close €7 on buy day; declared €7.06 -> plausible
        "ENEL.MI": [{"ts": "2024-04-18", "close": 7.0}],
    }
    holdings = [
        _h(id="a", symbol="MSFT", avg_price=400),                              # ~plausible
        _h(id="b", symbol="MSFT", avg_price=800),                              # ~+100% suspect
        _h(id="c", symbol="ENEL.MI", instrument_id="iid-ENEL.MI", currency="EUR",
           avg_price=7.06, buy_date="2024-04-18"),                            # plausible EUR
        _h(id="d", symbol="MSFT", buy_date=None),                             # no date -> unverifiable
        _h(id="e", symbol="ZZZ", instrument_id="iid-ZZZ", buy_date="2026-01-15"),  # no price -> unverifiable
    ]
    out = check_holdings(_Cfg(), _Store(holdings, prices), _Provider())
    by = {r["id"]: r for r in out["results"]}
    assert by["a"]["status"] == PLAUSIBLE and abs(by["a"]["market_eur"] - 400) < 1
    assert by["b"]["status"] == SUSPECT and by["b"]["deviation_pct"] > 0.9
    assert by["c"]["status"] == PLAUSIBLE
    assert by["d"]["status"] == UNVERIFIABLE and "data" in by["d"]["reason"]
    assert by["e"]["status"] == UNVERIFIABLE
    assert out["summary"][SUSPECT] == 1 and out["summary"][PLAUSIBLE] == 2
    # suspects sorted first
    assert out["results"][0]["status"] == SUSPECT


def test_closed_and_manual_rows_are_skipped():
    holdings = [_h(id="cl", status="closed"), _h(id="mn", valuation_mode="manual"),
                _h(id="z", quantity=0)]
    out = check_holdings(_Cfg(), _Store(holdings, {}), _Provider())
    assert out["results"] == []

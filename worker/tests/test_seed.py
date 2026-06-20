"""Seed idempotency: holdings must preserve user quantity/avg_price.

Uses an in-memory fake storage — no DB. Guards the rule that re-seeding
refreshes metadata but never zeroes the user-entered position figures.
"""
from app.config import AppConfig, Holding, Instrument
from app.ingestion.seed import seed_universe_and_holdings


class FakeStorage:
    def __init__(self):
        self.instruments = {}      # symbol -> row
        self.holdings = {}         # symbol -> row

    # instruments
    def upsert_instruments(self, rows):
        for r in rows:
            self.instruments[r["symbol"]] = r

    def get_instrument_id(self, symbol):
        return f"id-{symbol}" if symbol in self.instruments else None

    # holdings
    def list_holdings(self):
        return list(self.holdings.values())

    def insert_holdings(self, rows):
        for r in rows:
            assert r["symbol"] not in self.holdings, "double insert"
            self.holdings[r["symbol"]] = dict(r)

    def update_holding_metadata(self, symbol, metadata):
        assert "quantity" not in metadata and "avg_price" not in metadata
        self.holdings[symbol].update(metadata)


def _cfg():
    return AppConfig(
        base_currency="USD",
        account={"size": 1000},
        risk={},
        universe=[Instrument(symbol="GOOGL", name="Alphabet", asset_class="equity",
                             sleeve="equity", traded=True)],
        holdings=[
            Holding(symbol="GOOGL", quantity=0, avg_price=None, name="Alphabet",
                    asset_class="equity"),
            Holding(symbol="AVGO", quantity=0, avg_price=None, name="Broadcom",
                    asset_class="equity"),
        ],
        schedule={}, providers={}, indicators={},
    )


def test_first_seed_inserts_all_holdings():
    s = FakeStorage()
    seed_universe_and_holdings(_cfg(), s)
    assert set(s.holdings) == {"GOOGL", "AVGO"}
    assert s.holdings["GOOGL"]["quantity"] == 0
    # instrument_id resolved for universe symbol, None for off-universe holding
    assert s.holdings["GOOGL"]["instrument_id"] == "id-GOOGL"
    assert s.holdings["AVGO"]["instrument_id"] is None


def test_reseed_preserves_user_quantity_and_avg_price():
    s = FakeStorage()
    seed_universe_and_holdings(_cfg(), s)

    # user fills in real figures
    s.holdings["GOOGL"]["quantity"] = 42
    s.holdings["GOOGL"]["avg_price"] = 123.45

    # re-seed (e.g. config metadata tweak)
    seed_universe_and_holdings(_cfg(), s)

    # quantity/avg_price preserved; no duplicate rows
    assert s.holdings["GOOGL"]["quantity"] == 42
    assert s.holdings["GOOGL"]["avg_price"] == 123.45
    assert len(s.holdings) == 2
    # metadata still present/refreshed
    assert s.holdings["GOOGL"]["name"] == "Alphabet"
    assert s.holdings["GOOGL"]["source"] == "config"

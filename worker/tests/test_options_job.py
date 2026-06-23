"""Light test for the options ingestion job — provider fully mocked.

Verifies: IV/Greeks are recomputed per contract, underlyings without
options are skipped gracefully, and hedge proposals are built per holding.
No network / no yfinance.
"""
from app.config import AppConfig, Holding, Instrument
from app.ingestion.options_job import run_options_ingestion
from app.providers.options.base import OptionQuote

EXPIRY = "2026-09-30"


class FakeStorage:
    def __init__(self):
        self.chain = []
        self.hedges = []

    def upsert_options_chain(self, rows):
        self.chain.extend(rows)

    def replace_hedge_proposals(self, rows):
        self.hedges = list(rows)


class FakeProvider:
    name = "fake"

    def get_spot(self, underlying):
        return 100.0

    def list_expiries(self, underlying):
        # NVDA + QQQ have options; everything else does not.
        return [EXPIRY] if underlying in ("NVDA", "QQQ") else []

    def fetch_chain(self, underlying, expiry):
        out = []
        for k, (cb, ca, pb, pa) in {
            95: (7.0, 7.4, 2.0, 2.4),
            100: (4.0, 4.4, 4.0, 4.4),
            105: (2.0, 2.4, 7.0, 7.4),
        }.items():
            out.append(OptionQuote("call", k, cb, ca, (cb + ca) / 2, 10, 100))
            out.append(OptionQuote("put", k, pb, pa, (pb + pa) / 2, 10, 100))
        return out


def _cfg():
    return AppConfig(
        base_currency="USD", account={"size": 100000}, risk={}, holdings=[
            Holding(symbol="NVDA", quantity=100, asset_class="equity"),
        ],
        universe=[
            Instrument(symbol="NVDA", asset_class="equity"),
            Instrument(symbol="^NDX", asset_class="index"),   # -> proxy QQQ
            Instrument(symbol="NVO", asset_class="equity"),   # resolved but no chain
            Instrument(symbol="BTC-USD", asset_class="crypto"),  # excluded (no options/proxy)
        ],
        schedule={}, providers={}, indicators={},
        options={
            "risk_free_rate": 0.04, "expiries_count": 3, "strikes_window_pct": 0.5,
            "hedge": {"put_otm_pct": 0.05, "call_otm_pct": 0.05, "min_days": 0},
            "macro_proxies": {"^NDX": "QQQ"},
        },
    )


def test_chain_rows_have_recomputed_iv_and_greeks():
    storage = FakeStorage()
    res = run_options_ingestion(_cfg(), storage, FakeProvider())
    assert res["failed"] == 0
    assert len(storage.chain) > 0
    atm = [r for r in storage.chain if r["strike"] == 100 and r["option_type"] == "call"]
    assert atm, "expected an ATM call row"
    row = atm[0]
    assert row["implied_vol"] is not None and row["implied_vol"] > 0
    assert 0 < row["delta"] < 1 and row["gamma"] > 0 and row["vega"] > 0
    assert row["source"] == "fake"


def test_underlyings_without_options_are_skipped():
    storage = FakeStorage()
    res = run_options_ingestion(_cfg(), storage, FakeProvider())
    # NVO is resolved (equity) but the provider returns no expiries -> skipped,
    # not failed; BTC-USD is excluded earlier (no options/proxy).
    assert res["skipped"] >= 1
    assert all(r["underlying"] in ("NVDA", "QQQ") for r in storage.chain)


def test_hedge_proposals_built_for_holding():
    storage = FakeStorage()
    run_options_ingestion(_cfg(), storage, FakeProvider())
    kinds = {h["kind"] for h in storage.hedges if h["symbol"] == "NVDA"}
    assert {"protective_put", "collar"} <= kinds
    pp = next(h for h in storage.hedges if h["kind"] == "protective_put")
    assert pp["floor"] == 95            # put strike ~5% OTM
    assert pp["legs"] and pp["pct_covered"] == 100.0  # qty 100 -> covered

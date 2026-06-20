"""Seed instruments and holdings from config into storage.

Idempotent: instruments are upserted by symbol. Holdings refresh only
their METADATA (name, asset_class, instrument_id) — any quantity/avg_price
already entered by the user is preserved, never zeroed. New holdings are
inserted with the config defaults. Run at startup and on config changes.
"""
from __future__ import annotations

from ..config import AppConfig
from ..logging_setup import get_logger
from ..storage import Storage

log = get_logger("ingestion.seed")


def seed_universe_and_holdings(cfg: AppConfig, storage: Storage) -> None:
    instruments = [
        {
            "symbol": i.symbol,
            "name": i.name,
            "asset_class": i.asset_class,
            "exchange": i.exchange,
            "currency": i.currency,
            "sleeve": i.sleeve,
            "tradeable_on": i.tradeable_on,
            "traded": i.traded,
            "is_active": True,
        }
        for i in cfg.universe
    ]
    storage.upsert_instruments(instruments)

    existing = {h.get("symbol") for h in storage.list_holdings()}
    to_insert: list[dict] = []
    updated = 0
    for h in cfg.holdings:
        iid = storage.get_instrument_id(h.symbol)
        metadata = {
            "instrument_id": iid,
            "name": h.name,
            "asset_class": h.asset_class,
            "source": "config",
        }
        if h.symbol in existing:
            # Preserve user-entered quantity/avg_price; refresh metadata only.
            storage.update_holding_metadata(h.symbol, metadata)
            updated += 1
        else:
            to_insert.append(
                {
                    "symbol": h.symbol,
                    "quantity": h.quantity,
                    "avg_price": h.avg_price,
                    **metadata,
                }
            )
    storage.insert_holdings(to_insert)
    log.info(
        "Seed complete: %d instruments, %d holdings (%d new, %d preserved)",
        len(instruments), len(cfg.holdings), len(to_insert), updated,
    )

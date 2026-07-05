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
            "contract_multiplier": i.contract_multiplier,
            "is_active": True,
        }
        for i in cfg.universe
    ]
    storage.upsert_instruments(instruments)

    # Risk settings: config.yaml is the source of truth; mirror it into the
    # DB so the dashboard can read account size + limits (no browser storage).
    try:
        storage.upsert_risk_settings(
            {
                "base_currency": cfg.base_currency,
                "account_size": cfg.account_size,
                "max_risk_per_trade_pct": cfg.max_risk_per_trade_pct,
                "max_portfolio_heat_pct": cfg.max_portfolio_heat_pct,
                "max_concurrent_positions": cfg.max_concurrent_positions,
                "max_position_deadline_days": cfg.max_position_deadline_days,
                "deadline_warn_days": cfg.deadline_warn_days,
                "rr_min": cfg.rr_min,
                "event_warn_hours": cfg.event_warn_hours,
                # discipline gate (0016) — config.yaml is the source of truth
                "budget_day": cfg.budget_day,
                "budget_week": cfg.budget_week,
                "budget_month": cfg.budget_month,
                "budget_day_mode": cfg.budget_day_mode,
                "budget_week_mode": cfg.budget_week_mode,
                "budget_month_mode": cfg.budget_month_mode,
                "stop_atr_min_multiple": cfg.stop_atr_min_multiple,
                "set_aside_per_day": cfg.set_aside_per_day,
            }
        )
    except Exception as exc:  # noqa: BLE001 — older DB without 0007/0016; don't block seed
        log.warning("Could not seed risk_settings (apply migrations 0007+0016?): %s", exc)

    # Standing alert rules (M8): one toggleable row per category. Existing
    # rows (and the user's enabled toggle) are preserved.
    _STANDING_LABELS = {
        "risk": "Violazioni di rischio / stop bucato",
        "deadline": "Deadline in avvicinamento",
        "key_figure": "Nuove dichiarazioni key-figure",
        "universe_news": "News su strumenti dell'universo",
        "iv_spike": "IV ATM elevata",
    }
    try:
        cooldown = cfg.alert_cooldown_seconds
        rows = [
            {
                "kind": "standing",
                "standing_type": st,
                "enabled": bool(enabled),
                "cooldown_seconds": cooldown,
                "label": _STANDING_LABELS.get(st, st),
            }
            for st, enabled in cfg.standing_defaults.items()
        ]
        storage.upsert_standing_rules(rows)
    except Exception as exc:  # noqa: BLE001 — older DB without 0010; don't block seed
        log.warning("Could not seed standing alert rules (apply migration 0010?): %s", exc)

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

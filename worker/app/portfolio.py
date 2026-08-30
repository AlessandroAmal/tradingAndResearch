"""Real-portfolio backend: ISIN→ticker resolution + instrument/price/FX bootstrap.

Resolution order (never guesses silently — the UI confirms name+currency):
  1. the PERSISTED isin_map (a confirmed mapping is reused);
  2. the instruments table (the ticker is already in the universe);
  3. the lookup provider (Yahoo search), which may be empty or AMBIGUOUS.

Saving a holding ensures its instrument exists, ingests its prices AND the
EUR/<ccy> FX pair's prices (so the value shows immediately and updates with the
normal price job), and persists the confirmed ISIN mapping. Holdings are the
long book — SEPARATE from trade positions; they never enter trading risk heat.
The value/P&L math itself lives in the dashboard (lib/portfolio.js), computed
from the same prices — this module only bootstraps the data it needs.
"""
from __future__ import annotations

from typing import Any

from .config import AppConfig
from .logging_setup import get_logger
from .storage import Storage

log = get_logger("portfolio")


def base_currency(cfg: AppConfig) -> str:
    return str(cfg.portfolio.get("base_currency", "EUR")).upper()


def eur_pair_for(cfg: AppConfig, currency: str | None) -> str | None:
    """The EUR/<ccy> yfinance symbol used to convert this currency to EUR, or None
    for the base currency (rate 1) or an unmapped currency (value shown as n/d)."""
    if not currency:
        return None
    cur = currency.upper()
    if cur == base_currency(cfg):
        return None
    return (cfg.portfolio.get("eur_pairs", {}) or {}).get(cur)


def _looks_like_isin(q: str) -> bool:
    q = (q or "").strip().upper()
    return len(q) == 12 and q[:2].isalpha() and q.isalnum()


def resolve_symbol(storage: Storage, lookup, query: str) -> dict[str, Any]:
    """Resolve an ISIN or ticker to candidate(s) WITHOUT writing anything.

    Returns {query, is_isin, resolved, ambiguous, source, isin, ticker, name,
    currency, exchange, candidates:[...]}. `resolved` means a single confident
    match; `ambiguous` means the user must pick/confirm."""
    q = (query or "").strip()
    out: dict[str, Any] = {"query": q, "is_isin": _looks_like_isin(q),
                           "resolved": False, "ambiguous": False, "candidates": []}
    if not q:
        return out

    # 1. persisted mapping (by isin, else by ticker)
    hit = None
    if out["is_isin"]:
        hit = storage.get_isin_map(q.upper())
    if hit is None:
        hit = storage.find_isin_by_ticker(q)
    if hit:
        out.update(resolved=True, source="isin_map", isin=hit.get("isin"),
                   ticker=hit.get("ticker"), name=hit.get("name"),
                   currency=hit.get("currency"), exchange=hit.get("exchange"),
                   verified=bool(hit.get("verified")))
        return out

    # 2. the ticker is already an instrument in the universe
    if not out["is_isin"]:
        inst = _instrument_by_symbol(storage, q)
        if inst:
            out.update(resolved=True, source="instruments", ticker=inst["symbol"],
                       name=inst.get("name"), currency=inst.get("currency"),
                       exchange=inst.get("exchange"))
            return out
        # 2b. a user-supplied ticker not yet known: confirm via fast_info (reliable
        # even when ISIN search is blocked). We show name+currency for the user.
        desc = lookup.describe(q) if lookup else None
        if desc and (desc.currency or desc.name):
            out.update(resolved=True, source="ticker", ticker=desc.symbol,
                       name=desc.name, currency=desc.currency, exchange=desc.exchange)
            return out

    # 3. best-effort provider lookup (may be empty / ambiguous)
    cands = lookup.resolve(q) if lookup else []
    results = [{"symbol": c.symbol, "name": c.name, "currency": c.currency,
                "exchange": c.exchange, "quote_type": c.quote_type} for c in cands]
    out["candidates"] = results
    out["source"] = "yahoo"
    if len(results) == 1:
        c = results[0]
        cur = c.get("currency") or (lookup.currency_for(c["symbol"]) if lookup else None)
        out.update(resolved=True, ambiguous=False, ticker=c["symbol"], name=c.get("name"),
                   currency=cur, exchange=c.get("exchange"),
                   isin=q.upper() if out["is_isin"] else None)
    elif len(results) > 1:
        out["ambiguous"] = True
        out["isin"] = q.upper() if out["is_isin"] else None
    return out


def _instrument_by_symbol(storage: Storage, symbol: str) -> dict[str, Any] | None:
    for row in storage.list_instruments():
        if str(row.get("symbol", "")).upper() == symbol.upper():
            return row
    return None


def ingest_symbol_prices(storage: Storage, price_provider, symbol: str, *, days: int = 400) -> int:
    """Fetch + store daily prices for one symbol. Returns bars stored (0 on failure)."""
    iid = storage.get_instrument_id(symbol)
    if iid is None:
        return 0
    try:
        bars = price_provider.fetch_history(symbol, days)
    except Exception as exc:  # noqa: BLE001 — degrade: the value shows n/d
        log.warning("Portfolio price fetch failed for %s: %s", symbol, exc)
        return 0
    rows = [{"instrument_id": iid, "ts": b.ts.isoformat(), "open": b.open,
             "high": b.high, "low": b.low, "close": b.close, "volume": b.volume,
             "source": b.source} for b in bars]
    storage.upsert_prices(rows)
    return len(rows)


def ensure_instrument_and_prices(cfg: AppConfig, storage: Storage, price_provider,
                                 symbol: str, *, name: str | None, currency: str | None,
                                 asset_class: str | None = None,
                                 exchange: str | None = None) -> dict[str, Any]:
    """Upsert the instrument, ingest its prices, and ensure the EUR/<ccy> FX pair
    is present + priced too — so the holding is valuable right away."""
    inst = {"symbol": symbol, "name": name, "asset_class": asset_class or "equity",
            "currency": (currency or "USD").upper(), "exchange": exchange, "is_active": True}
    storage.upsert_instruments([{k: v for k, v in inst.items() if v is not None}])

    days = int(cfg.portfolio.get("history_days", 800))
    ingest_symbol_prices(storage, price_provider, symbol, days=days)

    pair = eur_pair_for(cfg, currency)
    fx_bars = 0
    if pair:
        storage.upsert_instruments([{"symbol": pair, "name": pair.replace("=X", ""),
                                     "asset_class": "fx", "currency": "EUR", "is_active": True}])
        fx_bars = ingest_symbol_prices(storage, price_provider, pair, days=days)
    return {"symbol": symbol, "fx_pair": pair, "fx_bars": fx_bars}


def save_holding(cfg: AppConfig, storage: Storage, price_provider, lookup,
                 payload: dict[str, Any]) -> dict[str, Any]:
    """Bootstrap instrument+prices+FX, persist the confirmed ISIN mapping, and
    upsert the holding. `payload`: {isin?, ticker/symbol, name, currency,
    asset_class?, exchange?, quantity, avg_price?, buy_date?, note?}."""
    symbol = (payload.get("ticker") or payload.get("symbol") or "").strip()
    if not symbol:
        raise ValueError("save_holding: ticker/symbol required")
    currency = (payload.get("currency") or "USD").upper()
    name = payload.get("name")
    asset_class = payload.get("asset_class")
    exchange = payload.get("exchange")

    boot = ensure_instrument_and_prices(cfg, storage, price_provider, symbol,
                                        name=name, currency=currency,
                                        asset_class=asset_class, exchange=exchange)

    # Persist the confirmed mapping (verified: the user accepted name+currency).
    # Best-effort: pre-0023 the table is absent — the holding still saves.
    try:
        storage.upsert_isin_map({
            "isin": payload.get("isin"), "ticker": symbol, "name": name,
            "currency": currency, "exchange": exchange,
            "source": "manual", "verified": True,
        })
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not persist isin_map (apply migration 0023?): %s", exc)

    holding = {
        "symbol": symbol, "isin": payload.get("isin"), "name": name,
        "asset_class": asset_class, "currency": currency,
        "avg_price_currency": (payload.get("avg_price_currency") or "EUR").upper(),
        "quantity": float(payload.get("quantity") or 0),
        "avg_price": _opt_float(payload.get("avg_price")),
        "buy_date": payload.get("buy_date") or None,
        "note": payload.get("note") or None,
        "instrument_id": storage.get_instrument_id(symbol),
        "source": "manual",
    }
    stored = storage.upsert_holding({k: v for k, v in holding.items() if v is not None})
    return {"holding": stored or holding, "bootstrap": boot}


def edit_holding(cfg: AppConfig, storage: Storage, price_provider, lookup,
                 holding_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Update one holding by id: quantity, avg_price, currency, buy_date, note,
    needs_review, and optionally a corrected TICKER. Changing the ticker re-points
    the instrument (pricing key), bootstraps its prices, and persists the corrected
    ISIN→ticker mapping as verified. Never an order."""
    updates: dict[str, Any] = {}
    for k in ("quantity", "avg_price", "avg_price_currency", "currency", "buy_date", "note", "needs_review"):
        if k in fields:
            updates[k] = fields[k]
    if updates.get("avg_price_currency"):
        updates["avg_price_currency"] = str(updates["avg_price_currency"]).upper()
    if "quantity" in updates and updates["quantity"] is not None:
        updates["quantity"] = float(updates["quantity"])
    if "avg_price" in updates:
        updates["avg_price"] = _opt_float(updates["avg_price"])

    new_ticker = (fields.get("ticker") or "").strip()
    if new_ticker:
        desc = lookup.describe(new_ticker) if lookup else None
        currency = fields.get("currency") or (desc.currency if desc else None)
        name = fields.get("name") or (desc.name if desc else None)
        ensure_instrument_and_prices(cfg, storage, price_provider, new_ticker,
                                     name=name, currency=currency, asset_class=fields.get("asset_class"))
        updates["instrument_id"] = storage.get_instrument_id(new_ticker)
        if currency:
            updates["currency"] = currency.upper()
        if name and not fields.get("name"):
            updates["name"] = name
        isin = fields.get("isin")
        try:
            storage.upsert_isin_map({"isin": isin, "ticker": new_ticker, "name": name,
                                     "currency": currency, "source": "manual", "verified": True})
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not persist corrected isin_map: %s", exc)

    stored = storage.update_holding_by_id(holding_id, updates)
    return {"holding": stored or {"id": holding_id, **updates}, "ticker_changed": bool(new_ticker)}


def _opt_float(v: Any) -> float | None:
    try:
        return float(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None

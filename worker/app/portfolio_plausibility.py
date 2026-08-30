"""Plausibility check for imported holdings — is the declared average cost near
the instrument's MARKET price on the declared buy date?

For each market-priced holding with a buy_date: get the historical close on that
date (stored prices first, else yfinance), convert to EUR at that day's FX, and
compare to the declared carico (EUR). Purely a sanity check against a hand-typed
sheet — NOT a substitute for the broker statement; a blended cost from several
tranches can legitimately diverge. Missing data → "non verificabile", never
estimated.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from .config import AppConfig
from .logging_setup import get_logger
from .portfolio import base_currency, eur_pair_for
from .storage import Storage

log = get_logger("portfolio.plausibility")

PLAUSIBLE = "plausibile"
SUSPECT = "sospetta"
UNVERIFIABLE = "non_verificabile"


def classify(declared_eur: float | None, market_eur: float | None,
             threshold: float) -> tuple[str, float | None]:
    """Compare the declared EUR cost to the market EUR price on the buy date.
    Within ±threshold → plausibile; beyond → sospetta; missing → non_verificabile."""
    if declared_eur is None or not market_eur:
        return UNVERIFIABLE, None
    dev = declared_eur / market_eur - 1.0
    return (PLAUSIBLE if abs(dev) <= threshold else SUSPECT), dev


def _num(v: Any) -> float | None:
    try:
        return float(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None


def _pick_close(asc: list[dict], on_date: str) -> float | None:
    """Nearest close at-or-before on_date from an ascending [{ts, close}] list."""
    picked = None
    for r in asc:
        if str(r["ts"])[:10] <= on_date:
            picked = r
        else:
            break
    return _num(picked["close"]) if picked else None


def _hist_close(storage: Storage, price_provider, symbol: str, on_date: str) -> float | None:
    """Historical close for `symbol` on `on_date`: stored prices if they cover it,
    else a yfinance fetch spanning the date. None if unavailable."""
    iid = storage.get_instrument_id(symbol)
    rows = storage.get_price_history(iid, 5000) if iid else []
    asc = sorted(({"ts": r["ts"], "close": r["close"]} for r in rows if r.get("close") is not None),
                 key=lambda r: str(r["ts"]))
    if asc and str(asc[0]["ts"])[:10] <= on_date:
        c = _pick_close(asc, on_date)
        if c is not None:
            return c
    try:
        days = (date.today() - date.fromisoformat(on_date)).days + 7
        bars = price_provider.fetch_history(symbol, max(days, 30))
        asc2 = sorted(({"ts": b.ts.isoformat(), "close": b.close} for b in bars if b.close is not None),
                      key=lambda r: r["ts"])
        return _pick_close(asc2, on_date)
    except Exception as exc:  # noqa: BLE001 — degrade to unverifiable
        log.warning("historical close %s @ %s failed: %s", symbol, on_date, exc)
        return None


def check_holdings(cfg: AppConfig, storage: Storage, price_provider,
                   threshold: float | None = None) -> dict[str, Any]:
    """Run the check over all open, market-priced holdings. Returns
    {threshold, results:[...], summary:{plausibile, sospetta, non_verificabile}}."""
    base = base_currency(cfg)
    if threshold is None:
        threshold = float(cfg.portfolio.get("plausibility_threshold", 0.15))
    inst_by_id = {i["id"]: i for i in storage.list_instruments()}
    results: list[dict] = []
    for h in storage.list_holdings():
        if h.get("status") == "closed" or h.get("valuation_mode") == "manual":
            continue
        if not (float(h.get("quantity") or 0) > 0):
            continue
        cur = (h.get("currency") or (inst_by_id.get(h.get("instrument_id")) or {}).get("currency") or base).upper()
        cost_cur = (h.get("avg_price_currency") or base).upper()
        avg = _num(h.get("avg_price"))
        buy = h.get("buy_date")
        item = {"id": h["id"], "symbol": h.get("symbol"), "name": h.get("name"),
                "currency": cur, "buy_date": buy, "declared_eur": None,
                "market_eur": None, "deviation_pct": None,
                "needs_review": bool(h.get("needs_review"))}
        if avg is None or not buy:
            results.append({**item, "status": UNVERIFIABLE,
                            "reason": "manca prezzo di carico o data d'acquisto"})
            continue
        psym = (inst_by_id.get(h.get("instrument_id")) or {}).get("symbol") or h.get("symbol")
        native = _hist_close(storage, price_provider, psym, buy)
        if native is None:
            results.append({**item, "status": UNVERIFIABLE,
                            "reason": "prezzo storico non disponibile alla data"})
            continue
        if cur == base:
            fx = 1.0
        else:
            pair = eur_pair_for(cfg, cur)
            fx = _hist_close(storage, price_provider, pair, buy) if pair else None
            if fx is None:
                results.append({**item, "status": UNVERIFIABLE,
                                "reason": "cambio storico non disponibile alla data"})
                continue
        market_eur = native / fx
        declared_eur = avg if cost_cur == base else avg / fx
        status, dev = classify(declared_eur, market_eur, threshold)
        results.append({**item, "status": status, "declared_eur": declared_eur,
                        "market_eur": market_eur, "deviation_pct": dev,
                        "native_close": native, "fx_buy": fx})
    summary = {PLAUSIBLE: 0, SUSPECT: 0, UNVERIFIABLE: 0}
    for r in results:
        summary[r["status"]] = summary.get(r["status"], 0) + 1
    # suspects first, then unverifiable, then plausible; suspects by |deviation| desc
    order = {SUSPECT: 0, UNVERIFIABLE: 1, PLAUSIBLE: 2}
    results.sort(key=lambda r: (order[r["status"]], -abs(r.get("deviation_pct") or 0)))
    return {"threshold": threshold, "results": results, "summary": summary}

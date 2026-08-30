"""CSV import for the real portfolio — parse, classify, resolve, preview, commit.

The CSV columns are: categoria, tipo, stato, isin, nome, quantita, prezzo_carico,
valuta, data_acquisto, valorizzazione (mercato|manuale), note.

Rules (from the user):
  * valorizzazione=manuale → NEVER fetch a price; value = quantity × prezzo_carico
    in the row currency (physical gold, house, mortgage, pensions, TFR, single bonds).
  * a MORTGAGE ("passività") is a LIABILITY → negative in the totals.
  * stato=Conclusa → import as CLOSED (history), not an open holding.
  * same ISIN in different categorie → keep SEPARATE (a sub-portfolio row is its
    own thing); Alphabet appears twice (two tranches) → keep both.
  * categoria "Portafogli Figli" → a distinct sub-portfolio (not the main book).
  * notes containing "VERIFICA" → flag for the user to check before confirming.
  * NEVER guess a ticker silently: ISIN→ticker suggestions are marked
    unverified; the preview asks the user to confirm/enter the ticker.

Resolution is best-effort: persisted isin_map → the note's "ticker X" hint →
a curated suggestion (unverified) → describe() via fast_info to confirm
name/currency/price. Unresolved rows are surfaced, not invented.
"""
from __future__ import annotations

import csv
import io
from typing import Any

from .logging_setup import get_logger

log = get_logger("portfolio.import")

# Curated ISIN→ticker suggestions for this book. US single stocks are deterministic
# (an ISIN maps to one primary listing); ETFs have several exchange listings, so
# their suggestion is a STARTING point the user must confirm in the preview.
SUGGESTED_TICKERS: dict[str, str] = {
    # US mega-caps / ADRs — deterministic
    "US02079K3059": "GOOGL", "US30303M1027": "META", "US70450Y1038": "PYPL",
    "US67066G1040": "NVDA", "US5949181045": "MSFT", "US98422D1054": "XPEV",
    "US11135F1012": "AVGO", "US5951121038": "MU",
    # EU / other single stocks
    "DK0062498333": "NOVO-B.CO", "IT0003128367": "ENEL.MI", "IT0005599938": "FCT.MI",
    "CNE100000296": "1211.HK",
    # UCITS ETFs / ETCs / ETNs — SUGGESTIONS, confirm the exchange listing
    "IE00BFMXXD54": "VUAA.DE", "IE00BYPLS672": "ISPY.MI", "IE00BK5BQT80": "VWCE.DE",
    "IE00BKM4GZ66": "IS3N.DE", "LU0908500753": "MEUD.PA", "IE0003Z9E2Y3": "COPX.MI",
    "LU0290355717": "XGLE.DE", "IE00B3VWN393": "IBTM.L", "GB00BJYDH287": "BTCW.MI",
    "IE00B579F325": "SGLD.L", "FR0013416716": "GLDA.PA", "JE00B1VS3333": "PHAG.L",
    "IE00B4ND3602": "SGLN.L",
    # IE00M7V94E1 (VanEck Uranium) omitted: the ISIN in the CSV is malformed (VERIFICARE).
}
DETERMINISTIC = {  # ISINs whose ticker is unambiguous (still confirmed via fast_info)
    "US02079K3059", "US30303M1027", "US70450Y1038", "US67066G1040", "US5949181045",
    "US98422D1054", "US11135F1012", "US5951121038", "DK0062498333", "IT0003128367",
}
SUBPORTFOLIO = "Portafogli Figli"


def parse_csv(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(text))
    for i, r in enumerate(reader):
        rows.append({
            "row": i + 2,  # 1-based incl header
            "categoria": (r.get("categoria") or "").strip(),
            "tipo": (r.get("tipo") or "").strip(),
            "stato": (r.get("stato") or "").strip(),
            "isin": (r.get("isin") or "").strip().upper() or None,
            "nome": (r.get("nome") or "").strip(),
            "quantita": _num(r.get("quantita")),
            "prezzo_carico": _num(r.get("prezzo_carico")),
            "valuta": (r.get("valuta") or "EUR").strip().upper(),
            "data_acquisto": (r.get("data_acquisto") or "").strip() or None,
            "valorizzazione": (r.get("valorizzazione") or "mercato").strip().lower(),
            "note": (r.get("note") or "").strip(),
        })
    return rows


def classify(row: dict[str, Any]) -> dict[str, Any]:
    note = (row.get("note") or "").lower()
    nome = (row.get("nome") or "").lower()
    manual = row.get("valorizzazione") == "manuale"
    closed = row.get("stato", "").lower().startswith("conclus")
    liability = ("passivit" in nome) or ("mutuo" in nome) or ("passivit" in note and "mutuo" in nome)
    return {
        "manual": manual,
        "closed": closed,
        "liability": liability,
        "verificare": "verifica" in note,
        "subportfolio": row.get("categoria") == SUBPORTFOLIO,
        # manual value = quantity × prezzo_carico (row currency); liability → negative
        "manual_value": _manual_value(row, liability) if manual else None,
        "note_ticker": _ticker_from_note(row.get("note")),
    }


def resolve_row(row: dict[str, Any], flags: dict[str, Any], storage, lookup) -> dict[str, Any]:
    """Resolve a MARKET row to a ticker (never a silent guess). Manual rows skip
    resolution. Returns {ticker, name, currency, source, verified, suggested}."""
    out: dict[str, Any] = {"ticker": None, "name": row.get("nome"),
                           "currency": row.get("valuta"), "source": None,
                           "verified": False, "suggested": False}
    if flags["manual"]:
        out["source"] = "manuale"
        return out
    isin = row.get("isin")
    # 1. persisted mapping
    hit = storage.get_isin_map(isin) if isin else None
    if hit and hit.get("ticker"):
        out.update(ticker=hit["ticker"], name=hit.get("name") or out["name"],
                   currency=hit.get("currency") or out["currency"], source="isin_map",
                   verified=bool(hit.get("verified")))
        return out
    # 2. explicit ticker hint in the note
    cand = flags.get("note_ticker")
    # 3. curated suggestion
    if not cand and isin:
        cand = SUGGESTED_TICKERS.get(isin)
        if cand:
            out["suggested"] = True
    if not cand:
        return out  # unresolved — the user must supply the ticker
    # confirm the candidate's name/currency via fast_info (reliable, unlike search)
    desc = lookup.describe(cand) if lookup else None
    out.update(ticker=cand,
               name=(desc.name if desc and desc.name else out["name"]),
               currency=(desc.currency if desc and desc.currency else out["currency"]),
               source=("note" if flags.get("note_ticker") else "suggested"),
               verified=bool(isin in DETERMINISTIC or flags.get("note_ticker")))
    return out


def build_preview(text: str, storage, lookup, price_provider=None,
                  overrides: dict | None = None) -> list[dict[str, Any]]:
    """Parse + classify + resolve every row. `overrides` maps a row number (str/int)
    to a user-chosen ticker. With a price_provider, also attaches a live price."""
    overrides = overrides or {}
    items = []
    for r in parse_csv(text):
        fl = classify(r)
        res = resolve_row(r, fl, storage, lookup)
        ov = overrides.get(str(r["row"])) or overrides.get(r["row"])
        if ov and not fl["manual"]:
            desc = lookup.describe(ov) if lookup else None
            res.update(ticker=ov, source="override", verified=True, suggested=False,
                       name=(desc.name if desc and desc.name else res["name"]),
                       currency=(desc.currency if desc and desc.currency else res["currency"]))
        price = None
        if price_provider and not fl["manual"] and res.get("ticker"):
            price = price_provider.latest_price(res["ticker"])
        items.append({**r, "flags": fl, "res": res, "price": price})
    return items


def _manual_symbol(row: dict[str, Any]) -> str:
    base = row.get("isin") or row.get("nome") or "manual"
    slug = "".join(c if c.isalnum() else "-" for c in str(base)).strip("-")[:40]
    return f"MANUAL:{slug}"


def commit_import(cfg, storage, price_provider, lookup, text: str,
                  overrides: dict | None = None) -> dict[str, Any]:
    """Persist the confirmed import. Idempotent: clears the previous CSV import
    first. Market rows bootstrap instrument+prices; manual/unresolved rows get a
    synthetic symbol and keep their manual value. Returns a summary."""
    from .portfolio import ensure_instrument_and_prices
    items = build_preview(text, storage, lookup, None, overrides)
    # Full reset: the real portfolio IS this CSV (config qty-0 placeholders re-seed
    # later). holdings has a unique(symbol) constraint, so several rows for the
    # same ticker (tranches / same ISIN in two categories) get a distinct display
    # `symbol` while `instrument_id` keeps pointing at the real instrument (used
    # for pricing). Drop the constraint via migration 0025 for clean symbols.
    storage.delete_all_holdings()
    inserted = 0
    unresolved: list[dict] = []
    seen: dict[str, int] = {}
    for it in items:
        r, fl, res = it, it["flags"], it["res"]
        market = not fl["manual"]
        ticker = res.get("ticker")
        status = "closed" if fl["closed"] else "open"
        base_symbol = ticker if (market and ticker) else _manual_symbol(r)
        seen[base_symbol] = seen.get(base_symbol, 0) + 1
        symbol = base_symbol if seen[base_symbol] == 1 else f"{base_symbol}#{r['row']}"
        if market and ticker and status == "open":
            ensure_instrument_and_prices(cfg, storage, price_provider, ticker,
                                         name=res.get("name"), currency=res.get("currency"),
                                         asset_class=r.get("tipo"))
            if r.get("isin"):
                try:
                    storage.upsert_isin_map({"isin": r["isin"], "ticker": ticker,
                                             "name": res.get("name"), "currency": res.get("currency"),
                                             "source": "csv", "verified": bool(res.get("verified"))})
                except Exception:  # noqa: BLE001
                    pass
        if market and not ticker:
            unresolved.append({"row": r["row"], "isin": r.get("isin"), "nome": r.get("nome")})
        holding = {
            "symbol": symbol, "isin": r.get("isin"), "name": res.get("name") or r.get("nome"),
            "asset_class": r.get("tipo"), "currency": res.get("currency") or r.get("valuta"),
            # the user's sheet is all in EUR: the carico is a EUR amount.
            "avg_price_currency": "EUR",
            "quantity": r.get("quantita") or 0, "avg_price": r.get("prezzo_carico"),
            "buy_date": r.get("data_acquisto"), "note": r.get("note"),
            "category": r.get("categoria"), "item_type": r.get("tipo"), "status": status,
            "valuation_mode": "manual" if fl["manual"] else "market",
            "manual_value": fl["manual_value"] if fl["manual"] else None,
            "is_liability": fl["liability"], "needs_review": fl["verificare"],
            "source": "csv",
            # instrument_id points at the REAL ticker's instrument (pricing key),
            # even when the display `symbol` was de-duplicated.
            "instrument_id": storage.get_instrument_id(ticker) if (market and ticker) else None,
        }
        storage.insert_holding_row({k: v for k, v in holding.items() if v is not None})
        inserted += 1
    return {"inserted": inserted, "total": len(items), "unresolved": unresolved}


def _manual_value(row: dict[str, Any], liability: bool) -> float | None:
    q, p = row.get("quantita"), row.get("prezzo_carico")
    if q is None or p is None:
        return None
    v = q * p
    return -abs(v) if liability else v


def _ticker_from_note(note: str | None) -> str | None:
    if not note:
        return None
    low = note.lower()
    if "ticker " in low:
        after = note[low.index("ticker ") + 7:].strip()
        tok = after.split()[0].strip().rstrip(",;") if after else ""
        return tok or None
    return None


def _num(v: Any) -> float | None:
    try:
        s = str(v).strip().replace(",", ".")
        return float(s) if s not in ("", "None") else None
    except (TypeError, ValueError):
        return None

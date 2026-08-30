"""Yahoo Finance symbol lookup (free, unofficial).

Uses the public Yahoo search endpoint to map an ISIN or free text to candidate
tickers, then reads the native currency via yfinance fast_info. Both are
best-effort and can fail or be ambiguous — the caller must let the user confirm.
Requires a browser-like User-Agent (Yahoo rejects the default).
"""
from __future__ import annotations

import httpx

from ...logging_setup import get_logger
from .base import LookupResult, SymbolLookupProvider

log = get_logger("provider.lookup.yahoo")

SEARCH_HOSTS = ("https://query1.finance.yahoo.com/v1/finance/search",
                "https://query2.finance.yahoo.com/v1/finance/search")
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")


def _looks_like_isin(q: str) -> bool:
    q = q.strip().upper()
    return len(q) == 12 and q[:2].isalpha() and q.isalnum()


class YahooLookupProvider(SymbolLookupProvider):
    name = "yahoo"

    def __init__(self, *, timeout: float = 12.0) -> None:
        self._timeout = timeout

    def resolve(self, query: str) -> list[LookupResult]:
        q = (query or "").strip()
        if not q:
            return []
        isin = q.upper() if _looks_like_isin(q) else None
        quotes = []
        for url in SEARCH_HOSTS:
            try:
                resp = httpx.get(
                    url,
                    params={"q": q, "quotesCount": 8, "newsCount": 0, "listsCount": 0},
                    headers={"User-Agent": _UA},
                    timeout=self._timeout,
                )
                resp.raise_for_status()
                quotes = resp.json().get("quotes") or []
                break
            except Exception as exc:  # noqa: BLE001 — best-effort; try next host
                log.warning("Yahoo lookup failed for %r via %s: %s", q, url, exc)
        if not quotes:
            return []

        out: list[LookupResult] = []
        for item in quotes:
            sym = item.get("symbol")
            if not sym:
                continue
            out.append(LookupResult(
                symbol=sym,
                name=item.get("shortname") or item.get("longname"),
                currency=None,                     # search omits it; filled on confirm
                exchange=item.get("exchDisp") or item.get("exchange"),
                quote_type=item.get("quoteType"),
                isin=isin,
                source=self.name,
            ))
        return out

    def currency_for(self, symbol: str) -> str | None:
        try:
            import yfinance as yf
            fi = getattr(yf.Ticker(symbol), "fast_info", None)
            if fi is None:
                return None
            cur = fi.get("currency") if hasattr(fi, "get") else fi["currency"]
            return str(cur).upper() if cur else None
        except Exception as exc:  # noqa: BLE001
            log.warning("currency_for(%s) failed: %s", symbol, exc)
            return None

    def describe(self, symbol: str) -> LookupResult | None:
        """Confirm a user-provided ticker: currency via fast_info (reliable), name
        + exchange best-effort. Returns None only if the ticker looks invalid
        (no currency and no price)."""
        try:
            import yfinance as yf
            t = yf.Ticker(symbol)
            fi = getattr(t, "fast_info", None)
            cur = None
            exch = None
            if fi is not None:
                try:
                    cur = fi.get("currency") if hasattr(fi, "get") else fi["currency"]
                    exch = fi.get("exchange") if hasattr(fi, "get") else None
                except (KeyError, TypeError):
                    cur = None
            name = None
            try:                                   # .info is slow/flaky — guard hard
                info = t.get_info() if hasattr(t, "get_info") else t.info
                name = (info or {}).get("longName") or (info or {}).get("shortName")
                cur = cur or ((info or {}).get("currency"))
                exch = exch or ((info or {}).get("exchange"))
            except Exception:  # noqa: BLE001
                pass
            if not cur and name is None:
                return None
            return LookupResult(symbol=symbol, name=name,
                                currency=str(cur).upper() if cur else None,
                                exchange=str(exch) if exch else None, source=self.name)
        except Exception as exc:  # noqa: BLE001
            log.warning("describe(%s) failed: %s", symbol, exc)
            return None

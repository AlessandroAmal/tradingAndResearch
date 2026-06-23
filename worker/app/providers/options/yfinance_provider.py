"""yfinance implementation of OptionsProvider.

Free, no key. yfinance serves option chains only for US equities/ETFs
(NVDA, TSLA, GOOGL, QQQ, GLD, …) — futures/FX/indices have none, so
`list_expiries` returns [] for them and the job degrades gracefully.

We deliberately IGNORE Yahoo's `impliedVolatility` column (unreliable) and
only read strike/bid/ask/last/volume/openInterest; IV is recomputed in
`app.options`.
"""
from __future__ import annotations

import pandas as pd
import yfinance as yf

from ...logging_setup import get_logger
from .base import OptionQuote, OptionsProvider

log = get_logger("provider.options.yfinance")


class YFinanceOptionsProvider(OptionsProvider):
    name = "yfinance"

    def get_spot(self, underlying: str) -> float | None:
        try:
            tk = yf.Ticker(underlying)
            fi = getattr(tk, "fast_info", None)
            if fi:
                px = fi.get("last_price") or fi.get("lastPrice")
                if px:
                    return float(px)
            hist = tk.history(period="1d", interval="1d")
            if hist is not None and not hist.empty:
                return float(hist["Close"].iloc[-1])
        except Exception as exc:  # noqa: BLE001
            log.warning("Spot lookup failed for %s: %s", underlying, exc)
        return None

    def list_expiries(self, underlying: str) -> list[str]:
        try:
            opts = yf.Ticker(underlying).options
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"list_expiries({underlying}) failed: {exc}") from exc
        return list(opts or [])

    def fetch_chain(self, underlying: str, expiry: str) -> list[OptionQuote]:
        try:
            chain = yf.Ticker(underlying).option_chain(expiry)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"fetch_chain({underlying},{expiry}) failed: {exc}") from exc

        quotes: list[OptionQuote] = []
        quotes.extend(_rows_to_quotes(chain.calls, "call"))
        quotes.extend(_rows_to_quotes(chain.puts, "put"))
        log.debug("Chain %s %s: %d quotes", underlying, expiry, len(quotes))
        return quotes


def _rows_to_quotes(df, option_type: str) -> list[OptionQuote]:
    if df is None or df.empty:
        return []
    out: list[OptionQuote] = []
    for _, row in df.iterrows():
        strike = _num(row.get("strike"))
        if strike is None:
            continue
        out.append(
            OptionQuote(
                option_type=option_type,
                strike=strike,
                bid=_num(row.get("bid")),
                ask=_num(row.get("ask")),
                last=_num(row.get("lastPrice")),
                volume=_num(row.get("volume")),
                open_interest=_num(row.get("openInterest")),
            )
        )
    return out


def _num(v: object) -> float | None:
    try:
        if v is None or pd.isna(v):  # type: ignore[arg-type]
            return None
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None

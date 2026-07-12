"""yfinance implementation of PriceProvider.

Free, no API key. yfinance is unofficial and can break/rate-limit, so
the ingestion job wraps calls with retry/backoff and clear logging.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

from ...logging_setup import get_logger
from .base import PriceBar, PriceProvider

log = get_logger("provider.prices.yfinance")


class YFinancePriceProvider(PriceProvider):
    name = "yfinance"

    def fetch_history(self, symbol: str, days: int) -> list[PriceBar]:
        period = f"{max(days, 1)}d"
        df = yf.Ticker(symbol).history(period=period, interval="1d", auto_adjust=False)
        if df is None or df.empty:
            raise RuntimeError(f"yfinance returned no data for {symbol!r}")

        bars: list[PriceBar] = []
        for idx, row in df.iterrows():
            ts = idx.to_pydatetime() if isinstance(idx, pd.Timestamp) else idx
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            else:
                ts = ts.astimezone(timezone.utc)
            bars.append(
                PriceBar(
                    symbol=symbol,
                    ts=ts,
                    open=_num(row.get("Open")),
                    high=_num(row.get("High")),
                    low=_num(row.get("Low")),
                    close=_num(row.get("Close")),
                    volume=_num(row.get("Volume")),
                    source=self.name,
                )
            )
        log.debug("Fetched %d bars for %s", len(bars), symbol)
        return bars

    def latest_price(self, symbol: str) -> float | None:
        """Near-live price via fast_info, falling back to the last 1m/1d close."""
        try:
            t = yf.Ticker(symbol)
            fi = getattr(t, "fast_info", None)
            if fi is not None:
                for key in ("last_price", "lastPrice", "regular_market_price"):
                    try:
                        v = _num(fi.get(key)) if hasattr(fi, "get") else _num(fi[key])
                    except (KeyError, TypeError):
                        v = None
                    if v:
                        return v
            intraday = t.history(period="1d", interval="1m", auto_adjust=False)
            if intraday is not None and not intraday.empty:
                return _num(intraday["Close"].iloc[-1])
            daily = t.history(period="5d", interval="1d", auto_adjust=False)
            if daily is not None and not daily.empty:
                return _num(daily["Close"].iloc[-1])
        except Exception as exc:  # noqa: BLE001 — never crash the experiment
            log.warning("latest_price(%s) failed: %s", symbol, exc)
        return None


def _num(v: object) -> float | None:
    try:
        if v is None or pd.isna(v):  # type: ignore[arg-type]
            return None
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None

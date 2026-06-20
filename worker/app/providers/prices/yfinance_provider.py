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


def _num(v: object) -> float | None:
    try:
        if v is None or pd.isna(v):  # type: ignore[arg-type]
            return None
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None

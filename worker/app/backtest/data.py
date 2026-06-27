"""Long-history loader for the research bench, with a local disk cache.

Reuses the existing PriceProvider interface (yfinance today) to pull many years
of daily OHLC, and caches each instrument to `data/local/backtest/` (git-ignored)
so repeated backtests don't re-hit the provider. The cache is refreshed when
older than `max_age_hours`.

No look-ahead logic lives here — this is raw OHLC. The engine enforces t+1 entry.
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from ..config import REPO_ROOT
from ..logging_setup import get_logger
from ..providers.prices import PriceProvider

log = get_logger("backtest.data")

DEFAULT_CACHE = REPO_ROOT / "data" / "local" / "backtest"


def _safe(symbol: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in symbol)


def _cache_path(symbol: str, cache_dir: Path) -> Path:
    return cache_dir / f"{_safe(symbol)}.csv"


def _fresh(path: Path, max_age_hours: float) -> bool:
    return path.exists() and (time.time() - path.stat().st_mtime) < max_age_hours * 3600


def load_history(
    symbol: str,
    provider: PriceProvider,
    *,
    days: int = 5475,            # ~15 years of calendar days
    cache_dir: Path | None = None,
    max_age_hours: float = 24.0,
    force: bool = False,
) -> pd.DataFrame:
    """Return an ascending OHLC DataFrame (date index) for `symbol`.

    Served from the disk cache when fresh; otherwise fetched via the provider and
    cached. Raises if neither the provider nor a cache yields data.
    """
    cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(symbol, cache_dir)

    if not force and _fresh(path, max_age_hours):
        log.debug("Backtest cache hit for %s (%s)", symbol, path.name)
        return _read_cache(path)

    try:
        bars = provider.fetch_history(symbol, days)
        df = _bars_to_df(bars)
        df.to_csv(path)
        log.info("Cached %d bars for %s -> %s", len(df), symbol, path.name)
        return df
    except Exception as exc:  # noqa: BLE001 — fall back to a stale cache if present
        if path.exists():
            log.warning("Fetch failed for %s (%s) — using stale cache", symbol, exc)
            return _read_cache(path)
        raise


def _bars_to_df(bars) -> pd.DataFrame:
    rows = [
        {"date": b.ts.date().isoformat(), "open": b.open, "high": b.high,
         "low": b.low, "close": b.close, "volume": b.volume}
        for b in bars
        if b.open is not None and b.close is not None
    ]
    if not rows:
        raise RuntimeError("no usable bars returned")
    df = pd.DataFrame(rows).drop_duplicates("date").set_index("date").sort_index()
    df.index = pd.to_datetime(df.index)
    return df


def _read_cache(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0)
    df.index = pd.to_datetime(df.index)
    return df.sort_index()

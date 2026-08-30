"""Price ingestion job: fetch OHLCV per universe symbol -> storage.

Per-symbol isolation: one symbol failing does not abort the others.
Failures are logged clearly and counted; the job returns a small summary.
"""
from __future__ import annotations

from ..config import AppConfig
from ..logging_setup import get_logger
from ..providers.prices import PriceProvider
from ..storage import Storage
from .retry import with_retry

log = get_logger("ingestion.prices")


def run_prices_ingestion(
    cfg: AppConfig, storage: Storage, provider: PriceProvider
) -> dict[str, int]:
    days = int(cfg.indicators.get("history_days", 250))
    ok, failed = 0, 0

    for symbol in cfg.symbols:
        try:
            iid = storage.get_instrument_id(symbol)
            if iid is None:
                log.warning("No instrument_id for %s — skipping (run seed?)", symbol)
                failed += 1
                continue

            bars = with_retry(
                lambda s=symbol: provider.fetch_history(s, days),
                label=f"fetch_history({symbol})",
            )
            # Skip bars with no close — a partial current-day bar (pre-market /
            # not-yet-finalised) would otherwise become the newest row with a null
            # close and read as "n/d" for a liquid instrument.
            rows = [
                {
                    "instrument_id": iid,
                    "ts": b.ts.isoformat(),
                    "open": b.open,
                    "high": b.high,
                    "low": b.low,
                    "close": b.close,
                    "volume": b.volume,
                    "source": b.source,
                }
                for b in bars
                if b.close is not None
            ]
            storage.upsert_prices(rows)
            ok += 1
        except Exception as exc:  # noqa: BLE001 — isolate per-symbol failures
            failed += 1
            log.error("Price ingestion failed for %s: %s", symbol, exc)

    log.info("Prices ingestion done: %d ok, %d failed", ok, failed)
    return {"ok": ok, "failed": failed}

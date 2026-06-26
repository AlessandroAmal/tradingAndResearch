"""Macro (FRED) ingestion job (M9).

Collects the FRED series referenced by the decision board config (the union of
every instrument's `macro_drivers` with source 'fred'), fetches each behind the
MacroProvider interface, and upserts the observations into `macro_series`.

Per-series isolation + retry/backoff + clear logging (CLAUDE.md standards): one
series failing does not abort the others, and the decision board still renders
from the last stored values.
"""
from __future__ import annotations

from ..config import AppConfig
from ..logging_setup import get_logger
from ..providers.macro import MacroProvider
from ..storage import Storage
from .retry import with_retry

log = get_logger("ingestion.macro")


def _configured_fred_series(cfg: AppConfig) -> list[str]:
    db_cfg = dict(cfg.raw.get("decision_board", {}) or {})
    ids: list[str] = []
    for inst in db_cfg.get("instruments", []) or []:
        for drv in inst.get("macro_drivers", []) or []:
            if (drv.get("source") or "fred").lower() == "fred":
                sid = drv.get("id")
                if sid and sid not in ids:
                    ids.append(sid)
    return ids


def run_macro_ingestion(
    cfg: AppConfig, storage: Storage, provider: MacroProvider
) -> dict[str, int]:
    db_cfg = dict(cfg.raw.get("decision_board", {}) or {})
    days = int(dict(db_cfg.get("macro", {}) or {}).get("history_days", 365))
    series_ids = _configured_fred_series(cfg)
    if not series_ids:
        log.info("No FRED series configured (decision_board.*.macro_drivers) — skipping.")
        return {"ok": 0, "failed": 0}

    ok = failed = 0
    for sid in series_ids:
        try:
            obs = with_retry(
                lambda s=sid: provider.fetch_series(s, days=days),
                label=f"fred({sid})",
            )
            rows = [
                {
                    "series_id": o.series_id,
                    "obs_date": o.obs_date.isoformat(),
                    "value": o.value,
                    "source": o.source,
                }
                for o in obs
                if o.value is not None  # store only real observations
            ]
            storage.upsert_macro_series(rows)
            ok += 1
            log.info("Macro %s: %d observations stored", sid, len(rows))
        except Exception as exc:  # noqa: BLE001 — isolate per-series
            failed += 1
            log.error("Macro ingestion failed for %s: %s", sid, exc)

    log.info("Macro ingestion done: %d ok, %d failed", ok, failed)
    return {"ok": ok, "failed": failed}

"""Macro (FRED) ingestion job (M9).

Collects the FRED series referenced by the decision board config (the union of
every instrument's `macro_drivers` with source 'fred'), fetches each behind the
MacroProvider interface, and upserts the observations into `macro_series`.

Also computes any DERIVED series declared in `decision_board.macro.derived`
(e.g. the Fed–ECB policy-rate differential FED_ECB_SPREAD = DFEDTARU − ECBDFR,
the main EUR/USD driver). A derived id is referenced by drivers like any other
series; here we fetch its components and store the computed series.

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


def _derived_specs(cfg: AppConfig) -> list[dict]:
    db_cfg = dict(cfg.raw.get("decision_board", {}) or {})
    return list(dict(db_cfg.get("macro", {}) or {}).get("derived", []) or [])


def _configured_fred_series(cfg: AppConfig, exclude: set[str]) -> list[str]:
    """Driver ids with source 'fred', excluding derived ids (those are computed)."""
    db_cfg = dict(cfg.raw.get("decision_board", {}) or {})
    ids: list[str] = []
    for inst in db_cfg.get("instruments", []) or []:
        for drv in inst.get("macro_drivers", []) or []:
            if (drv.get("source") or "fred").lower() == "fred":
                sid = drv.get("id")
                if sid and sid not in ids and sid not in exclude:
                    ids.append(sid)
    return ids


def run_macro_ingestion(
    cfg: AppConfig, storage: Storage, provider: MacroProvider
) -> dict[str, int]:
    db_cfg = dict(cfg.raw.get("decision_board", {}) or {})
    days = int(dict(db_cfg.get("macro", {}) or {}).get("history_days", 365))
    derived = _derived_specs(cfg)
    derived_ids = {d.get("id") for d in derived}
    direct_ids = _configured_fred_series(cfg, exclude=derived_ids)
    # Components needed only to compute derived series (fetched, not necessarily stored).
    component_ids = {c for d in derived for c in (d.get("left"), d.get("right")) if c}
    to_fetch = list(dict.fromkeys([*direct_ids, *component_ids]))  # unique, ordered

    if not to_fetch and not derived:
        log.info("No FRED series configured (decision_board.*.macro_drivers) — skipping.")
        return {"ok": 0, "failed": 0}

    cache: dict[str, list] = {}
    ok = failed = 0
    for sid in to_fetch:
        try:
            obs = with_retry(lambda s=sid: provider.fetch_series(s, days=days), label=f"fred({sid})")
            cache[sid] = obs
            if sid in direct_ids:
                storage.upsert_macro_series(_rows(obs))
                ok += 1
                log.info("Macro %s: %d observations stored", sid, len([o for o in obs if o.value is not None]))
        except Exception as exc:  # noqa: BLE001 — isolate per-series
            failed += 1
            log.error("Macro ingestion failed for %s: %s", sid, exc)

    # Derived series (e.g. FED_ECB_SPREAD).
    for spec in derived:
        sid = spec.get("id")
        try:
            rows = _compute_derived(spec, cache)
            if rows:
                storage.upsert_macro_series(rows)
                ok += 1
                log.info("Macro derived %s: %d observations stored", sid, len(rows))
            else:
                log.warning("Derived %s: no overlapping component data — skipped", sid)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            log.error("Derived series %s failed: %s", sid, exc)

    log.info("Macro ingestion done: %d ok, %d failed", ok, failed)
    return {"ok": ok, "failed": failed}


def _rows(obs) -> list[dict]:
    return [
        {"series_id": o.series_id, "obs_date": o.obs_date.isoformat(),
         "value": o.value, "source": o.source}
        for o in obs if o.value is not None
    ]


def _compute_derived(spec: dict, cache: dict[str, list]) -> list[dict]:
    """Compute a derived series from two fetched components.

    Aligns by date with carry-forward (rates are step functions, with different
    reporting frequencies/holidays), then applies `op` (default subtract).
    """
    sid, left_id, right_id = spec.get("id"), spec.get("left"), spec.get("right")
    op = (spec.get("op") or "subtract").lower()
    left = {o.obs_date: o.value for o in cache.get(left_id, []) if o.value is not None}
    right = {o.obs_date: o.value for o in cache.get(right_id, []) if o.value is not None}
    if not left or not right:
        return []

    rows: list[dict] = []
    lv = rv = None
    for d in sorted(set(left) | set(right)):
        if d in left:
            lv = left[d]
        if d in right:
            rv = right[d]
        if lv is None or rv is None:
            continue
        value = (lv - rv) if op == "subtract" else (lv + rv) if op == "add" else (lv - rv)
        rows.append({"series_id": sid, "obs_date": d.isoformat(), "value": value, "source": "derived"})
    return rows

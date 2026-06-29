"""CFTC implementation of PositioningProvider — Commitments of Traders (COT).

Free public Socrata API (no key). Uses the **TFF Futures-Only** dataset
(`gpe5-46if`) and the **Leveraged Funds** category for a market (default
'EURO FX'). Verified field names (2026): `report_date_as_yyyy_mm_dd`,
`market_and_exchange_names`, `lev_money_positions_long`, `lev_money_positions_short`,
`open_interest_all`.

Caveats (surfaced in the UI, not here): the report is released Friday for the
Tuesday snapshot (a lag), it is a swing/positioning signal not intraday, and it
is only useful CONTRARIAN at the extremes. Results are cached locally.
"""
from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import httpx

from ...config import REPO_ROOT
from ...logging_setup import get_logger
from .base import CotReport, PositioningProvider

log = get_logger("provider.positioning.cftc")

RESOURCE = "https://publicreporting.cftc.gov/resource/{dataset}.json"
DEFAULT_CACHE = REPO_ROOT / "data" / "local" / "cot"

# COT comes in two reports with different datasets, trader categories and field
# names. FINANCIAL futures (FX, rates, equity indices) -> TFF / Leveraged Funds.
# COMMODITIES (copper, gold, …) -> Disaggregated / Managed Money. The instrument
# config selects the report; this keeps the provider instrument-driven.
REPORTS = {
    "tff": {
        "dataset": "gpe5-46if",
        "long": "lev_money_positions_long", "short": "lev_money_positions_short",
    },
    "disaggregated": {
        "dataset": "72hh-3qpy",
        "long": "m_money_positions_long_all", "short": "m_money_positions_short_all",
    },
}


class CftcPositioningProvider(PositioningProvider):
    name = "cftc"

    def __init__(self, *, cache_dir: Path | None = None, max_age_hours: float = 24.0,
                 timeout: float = 20.0) -> None:
        self._cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE
        self._max_age_hours = max_age_hours
        self._timeout = timeout

    def fetch_history(self, market_query: str, *, lookback_weeks: int,
                      report: str = "tff") -> list[CotReport]:
        import json

        rep = REPORTS.get(report)
        if rep is None:
            raise ValueError(f"Unknown COT report {report!r} (known: {sorted(REPORTS)})")

        self._cache_dir.mkdir(parents=True, exist_ok=True)
        safe = "".join(c if c.isalnum() else "_" for c in f"{report}_{market_query}")
        path = self._cache_dir / f"{safe}.json"
        if path.exists() and (time.time() - path.stat().st_mtime) < self._max_age_hours * 3600:
            return _parse_rows(json.loads(path.read_text()), rep["long"], rep["short"])

        params = {
            "$where": f"market_and_exchange_names like '%{market_query}%'",
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": str(max(lookback_weeks, 1)),
        }
        try:
            resp = httpx.get(RESOURCE.format(dataset=rep["dataset"]), params=params, timeout=self._timeout)
            resp.raise_for_status()
            rows = resp.json()
            path.write_text(json.dumps(rows))
            return _parse_rows(rows, rep["long"], rep["short"])
        except Exception as exc:  # noqa: BLE001 — fall back to a stale cache
            if path.exists():
                log.warning("CFTC fetch failed (%s) — using stale cache", exc)
                return _parse_rows(json.loads(path.read_text()), rep["long"], rep["short"])
            raise


def _parse_rows(rows: list[dict], long_field: str, short_field: str) -> list[CotReport]:
    """Parse Socrata rows into CotReports (net = long − short), oldest→newest."""
    out: list[CotReport] = []
    for r in rows:
        d = _date(r.get("report_date_as_yyyy_mm_dd"))
        lng = _num(r.get(long_field))
        sht = _num(r.get(short_field))
        if d is None:
            continue
        net = (lng - sht) if (lng is not None and sht is not None) else None
        out.append(CotReport(report_date=d, long=lng, short=sht, net=net,
                             open_interest=_num(r.get("open_interest_all")), source="cftc"))
    out.sort(key=lambda c: c.report_date)
    return out


def _date(s) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def _num(v) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None

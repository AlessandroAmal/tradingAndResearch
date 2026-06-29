"""yfinance implementation of FundamentalsProvider (free, no key).

Reads `Ticker.info` + `get_earnings_dates`, maps to a structured dict with plain
keys. Every field degrades to None ("n/d") if absent. Cached locally (slow-moving
data). The mapping (`parse_fundamentals`) is pure and unit-tested with a fake info
dict — no network in tests.
"""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from ...config import REPO_ROOT
from ...logging_setup import get_logger
from .base import FundamentalsProvider

log = get_logger("provider.fundamentals.yfinance")
DEFAULT_CACHE = REPO_ROOT / "data" / "local" / "fundamentals"


def _num(v: Any) -> float | None:
    try:
        if v is None:
            return None
        f = float(v)
        return None if f != f else f  # drop NaN
    except (TypeError, ValueError):
        return None


def parse_fundamentals(info: dict, earnings: dict | None = None) -> dict:
    """Pure mapping from a yfinance `info` dict (+ earnings) to our structure.
    Missing -> None. `earnings` = {next_date, next_eps_estimate, surprises[]}."""
    info = info or {}
    earnings = earnings or {}
    return {
        "valuation": {
            "pe_trailing": _num(info.get("trailingPE")),
            "pe_forward": _num(info.get("forwardPE")),
            "ps": _num(info.get("priceToSalesTrailing12Months")),
            "pb": _num(info.get("priceToBook")),
        },
        "growth": {
            "revenue_yoy": _num(info.get("revenueGrowth")),
            "earnings_yoy": _num(info.get("earningsGrowth")
                                 if info.get("earningsGrowth") is not None
                                 else info.get("earningsQuarterlyGrowth")),
        },
        "quality": {
            "gross_margin": _num(info.get("grossMargins")),
            "operating_margin": _num(info.get("operatingMargins")),
            "net_margin": _num(info.get("profitMargins")),
            "roe": _num(info.get("returnOnEquity")),
        },
        "cash": {
            "free_cash_flow": _num(info.get("freeCashflow")),
            "operating_cash_flow": _num(info.get("operatingCashflow")),
            "cash": _num(info.get("totalCash")),
            "debt": _num(info.get("totalDebt")),
            "debt_to_equity": _num(info.get("debtToEquity")),
        },
        "earnings": {
            "eps_trailing": _num(info.get("trailingEps")),
            "eps_forward": _num(info.get("forwardEps")),
            "next_date": earnings.get("next_date"),
            "next_eps_estimate": earnings.get("next_eps_estimate"),
            "surprises": earnings.get("surprises", []),
        },
        "analysts": {
            "target_mean": _num(info.get("targetMeanPrice")),
            "target_high": _num(info.get("targetHighPrice")),
            "target_low": _num(info.get("targetLowPrice")),
            "n_analysts": _num(info.get("numberOfAnalystOpinions")),
            "recommendation": info.get("recommendationKey"),
            "recommendation_mean": _num(info.get("recommendationMean")),
        },
        "note": "Quadro dell'azienda e della valutazione — già riflesso nel prezzo, NON una previsione.",
    }


def _earnings_block(symbol: str, today: date) -> dict:
    """Next earnings date + EPS consensus + recent surprises from yfinance."""
    try:
        import yfinance as yf

        df = yf.Ticker(symbol).get_earnings_dates(limit=12)
    except Exception as exc:  # noqa: BLE001
        log.warning("earnings block %s failed: %s", symbol, exc)
        return {}
    if df is None or getattr(df, "empty", True):
        return {}
    next_date = next_est = None
    surprises: list[dict] = []
    for idx, row in df.iterrows():
        d = idx.date() if hasattr(idx, "date") else None
        if d is None:
            continue
        est = _num(row.get("EPS Estimate"))
        rep = _num(row.get("Reported EPS"))
        sur = _num(row.get("Surprise(%)"))
        if d >= today and rep is None:
            # nearest upcoming with an estimate
            if next_date is None or d < next_date:
                next_date, next_est = d, est
        elif rep is not None:
            surprises.append({"date": d.isoformat(), "reported": rep, "estimate": est,
                              "surprise_pct": sur, "beat": (sur is not None and sur > 0)})
    surprises.sort(key=lambda s: s["date"], reverse=True)
    return {"next_date": next_date.isoformat() if next_date else None,
            "next_eps_estimate": next_est, "surprises": surprises[:6]}


class YFinanceFundamentalsProvider(FundamentalsProvider):
    name = "yfinance"

    def __init__(self, *, cache_dir: Path | None = None, max_age_hours: float = 24.0) -> None:
        self._cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE
        self._max_age_hours = max_age_hours

    def fetch(self, symbol: str) -> dict:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        safe = "".join(c if c.isalnum() else "_" for c in symbol)
        path = self._cache_dir / f"{safe}.json"
        if path.exists() and (time.time() - path.stat().st_mtime) < self._max_age_hours * 3600:
            return json.loads(path.read_text())

        import yfinance as yf

        today = datetime.now(timezone.utc).date()
        try:
            info = dict(yf.Ticker(symbol).info or {})
        except Exception as exc:  # noqa: BLE001
            log.warning("fundamentals info %s failed: %s", symbol, exc)
            info = {}
        data = parse_fundamentals(info, _earnings_block(symbol, today))
        data["as_of"] = datetime.now(timezone.utc).isoformat()
        try:
            path.write_text(json.dumps(data, default=str))
        except Exception:  # noqa: BLE001
            pass
        return data

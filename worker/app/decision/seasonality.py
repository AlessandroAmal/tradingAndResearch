"""Ciclicità — seasonality / recurring calendar patterns. PURE & TESTED.

Seasonality is the home turf of data-snooping: slice time enough ways and SOMETHING
always looks cyclical. So this module is built to be honest, not impressive:
  * every bucket shows its sample size `n`;
  * buckets below a minimum sample are `sufficient=False` → no conclusion;
  * a rough significance flag (|t| > 2) is exposed BUT the fixed caveat reminds
    that multiple testing inflates it — it is never presented as a forecast;
  * when nothing clears the bar, we say so explicitly.

Monthly returns are month-end-to-month-end (consecutive months only); weekday
returns are daily. No directional probability is ever produced.

Tested in `worker/tests/test_seasonality.py`.
"""
from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from datetime import date

MONTHS_IT = ["gen", "feb", "mar", "apr", "mag", "giu",
             "lug", "ago", "set", "ott", "nov", "dic"]
WEEKDAYS_IT = ["lun", "mar", "mer", "gio", "ven"]

SEASONALITY_CAVEAT = (
    "La stagionalità è il regno del data-snooping: con abbastanza fette temporali "
    "qualcosa sembra SEMPRE ciclico. Sotto la soglia di campione → «insufficiente». "
    "Il flag di significatività (|t|>2) non corregge i test multipli. NON è una previsione."
)


def _to_date(v) -> date | None:
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def _t_stat(vals: Sequence[float]) -> float | None:
    n = len(vals)
    if n < 2:
        return None
    m = sum(vals) / n
    var = sum((x - m) ** 2 for x in vals) / (n - 1)
    sd = math.sqrt(var)
    if sd == 0:
        return None
    return m / (sd / math.sqrt(n))


def _bucket_stats(returns_by_key: dict[int, list[float]], labels: list[str],
                  min_sample: int) -> list[dict]:
    out: list[dict] = []
    for key in range(len(labels)):
        vals = returns_by_key.get(key, [])
        n = len(vals)
        t = _t_stat(vals)
        sufficient = n >= min_sample
        out.append({
            "key": key,
            "label": labels[key],
            "n": n,
            "mean_return": (sum(vals) / n) if n else None,
            "pct_up": (sum(1 for v in vals if v > 0) / n) if n else None,
            "t_stat": t,
            "sufficient": sufficient,
            "significant": bool(sufficient and t is not None and abs(t) > 2),
        })
    return out


def _next_month(ym: tuple[int, int]) -> tuple[int, int]:
    y, m = ym
    return (y + 1, 1) if m == 12 else (y, m + 1)


def monthly_seasonality(dates_iso: Sequence[str], closes: Sequence[float],
                        *, min_sample: int = 8) -> list[dict]:
    """Month-end→month-end returns bucketed by calendar month (consecutive only)."""
    last_close: dict[tuple[int, int], float] = {}
    for d_iso, c in zip(dates_iso, closes):
        d = _to_date(d_iso)
        if d is not None and c is not None:
            last_close[(d.year, d.month)] = float(c)   # dates ascending -> keeps month end
    keys = sorted(last_close)
    rets: dict[int, list[float]] = defaultdict(list)
    for i in range(1, len(keys)):
        prev, cur = keys[i - 1], keys[i]
        if cur != _next_month(prev):          # skip gaps: only consecutive months
            continue
        pc = last_close[prev]
        if pc > 0:
            rets[cur[1] - 1].append(last_close[cur] / pc - 1.0)   # month index 0..11
    return _bucket_stats(rets, MONTHS_IT, min_sample)


def weekday_seasonality(dates_iso: Sequence[str], closes: Sequence[float],
                        *, min_sample: int = 30) -> list[dict]:
    """Daily returns bucketed by weekday (Mon..Fri)."""
    rets: dict[int, list[float]] = defaultdict(list)
    for i in range(1, len(closes)):
        d = _to_date(dates_iso[i])
        pc = closes[i - 1]
        if d is not None and d.weekday() < 5 and pc and pc > 0:
            rets[d.weekday()].append(closes[i] / pc - 1.0)
    return _bucket_stats(rets, WEEKDAYS_IT, min_sample)


def compute_seasonality(dates_iso: Sequence[str], closes: Sequence[float],
                        *, month_min: int = 8, weekday_min: int = 30) -> dict:
    """Assemble monthly + weekday seasonality with the honesty scaffolding."""
    if not closes or len(closes) < 2:
        return {"available": False, "caveat": SEASONALITY_CAVEAT,
                "note": "Storico insufficiente per la stagionalità."}
    monthly = monthly_seasonality(dates_iso, closes, min_sample=month_min)
    weekday = weekday_seasonality(dates_iso, closes, min_sample=weekday_min)
    d0, d1 = _to_date(dates_iso[0]), _to_date(dates_iso[-1])
    years = round((d1 - d0).days / 365.25, 1) if (d0 and d1) else None
    any_sig = any(b["significant"] for b in monthly + weekday)
    return {
        "available": True,
        "years": years,
        "monthly": monthly,
        "weekday": weekday,
        "month_min": month_min,
        "weekday_min": weekday_min,
        "any_significant": any_sig,
        "caveat": SEASONALITY_CAVEAT,
        "note": (None if any_sig else
                 "Nessun pattern stagionale supera la soglia (campione sufficiente + |t|>2): "
                 "coerente col fatto che la stagionalità raramente è un vero edge."),
    }

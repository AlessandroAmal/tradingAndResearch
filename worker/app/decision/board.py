"""Decision board assembly + snapshot (M9).

For each configured instrument (gold today), assemble:
  - macro drivers (FRED series from macro_series + price gauges like ^VIX),
  - technicals (app.technicals),
  - the honest historical base rate for the current streak (app.base_rates),
  - option-implied probabilities at several horizons (app.decision.implied),
  - upcoming calendar events + recent key-figure statements (e.g. Powell),
  - optional NON-directional AI synthesis,
and save one snapshot per instrument for the dashboard.

NOT a signal, NEVER a prediction. The board is the picture the user weighs
(CLAUDE.md §1, §5). Generalises to any instrument by editing config only.

Macro reads come from the macro_series table (populated by the macro job), so
the board still renders from the last stored values even if FRED is down.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..config import AppConfig
from ..logging_setup import get_logger
from ..base_rates import STREAK_CAVEAT, streak_base_rate
from ..providers.options import OptionsProvider
from ..storage import Storage
from .. import technicals as tech
from .implied import implied_probabilities
from .synthesis import confluence_read

log = get_logger("decision.board")


# --- macro driver resolution -----------------------------------------
def _direction(latest: float | None, prev: float | None) -> str:
    if latest is None or prev is None:
        return "flat"
    if latest > prev:
        return "up"
    if latest < prev:
        return "down"
    return "flat"


def _driver_state(direction: str, supportive_when: str | None) -> str:
    """Map a driver's move to a context colour (NOT a buy/sell signal).

    'tailwind' = the move is historically supportive for this instrument,
    'headwind' = the opposite, 'neutral' = flat/unknown. Purely descriptive.
    """
    if not supportive_when or direction == "flat":
        return "neutral"
    good = "up" if supportive_when == "rising" else "down"
    return "tailwind" if direction == good else "headwind"


def _resolve_macro_driver(storage: Storage, drv: dict, days: int) -> dict:
    sid = drv.get("id")
    source = (drv.get("source") or "fred").lower()
    latest = prev = None
    as_of = None
    if source == "price":
        iid = storage.get_instrument_id(sid)
        rows = storage.get_price_history(iid, 2) if iid else []
        closes = [r.get("close") for r in rows if r.get("close") is not None]
        if closes:
            latest = float(closes[0])
            as_of = rows[0].get("ts")
        if len(closes) > 1:
            prev = float(closes[1])
    else:  # fred (default)
        rows = storage.get_macro_series(sid, days)  # newest-first
        vals = [(r.get("value"), r.get("obs_date")) for r in rows if r.get("value") is not None]
        if vals:
            latest, as_of = float(vals[0][0]), vals[0][1]
        if len(vals) > 1:
            prev = float(vals[1][0])
    direction = _direction(latest, prev)
    change = (latest - prev) if (latest is not None and prev is not None) else None
    return {
        "id": sid,
        "label": drv.get("label", sid),
        "source": source,
        "value": latest,
        "prev": prev,
        "change": change,
        "direction": direction,
        "state": _driver_state(direction, drv.get("supportive_when")),
        "supportive_when": drv.get("supportive_when"),
        "interpretation": drv.get("interpretation"),
        "as_of": str(as_of) if as_of is not None else None,
    }


def _filter_events(events: list[dict], keywords: list[str], limit: int) -> list[dict]:
    if not keywords:
        return events[:limit]
    kws = [k.lower() for k in keywords]
    out = [e for e in events if any(k in (e.get("title") or "").lower() for k in kws)]
    return out[:limit]


# --- confluence board ------------------------------------------------
def build_confluence(
    drivers: list[dict],
    technicals: dict,
    base_rate: dict,
    next_event: dict | None,
) -> list[dict]:
    """Flatten the inputs into at-a-glance condition rows (state-coloured).

    Each row is descriptive context, not a recommendation. `state` ∈
    {tailwind, headwind, watch, neutral} drives colour only.
    """
    rows: list[dict] = []

    # Macro drivers (factual direction + supportive/headwind context).
    for d in drivers:
        arrow = {"up": "↑", "down": "↓", "flat": "→"}.get(d["direction"], "→")
        rows.append({
            "key": f"macro:{d['id']}",
            "label": d["label"],
            "value": d["value"],
            "detail": f"{arrow} {d['interpretation'] or ''}".strip(),
            "state": d["state"],
        })

    # Streak (attention if currently extended).
    sk = technicals.get("streak", {})
    if sk.get("length"):
        rows.append({
            "key": "streak",
            "label": "Streak",
            "value": f"{sk['length']} giorni {('su' if sk['direction']=='up' else 'giù')}",
            "detail": "Run di giorni consecutivi nella stessa direzione.",
            "state": "watch" if sk["length"] >= 5 else "neutral",
        })

    # Position vs MA200 (trend context — factual above/below).
    ma200 = next((m for m in technicals.get("ma", []) if m.get("period") == 200), None)
    if ma200 and ma200.get("above") is not None:
        rows.append({
            "key": "ma200",
            "label": "vs MA200",
            "value": ("sopra" if ma200["above"] else "sotto")
            + (f" ({ma200['distance_pct']:+.1f}%)" if ma200.get("distance_pct") is not None else ""),
            "detail": "Posizione rispetto alla media a 200 giorni (contesto di tendenza).",
            "state": "neutral",
        })

    # RSI (attention only at the configured extremes).
    rsi = technicals.get("rsi", {})
    if rsi.get("value") is not None:
        rows.append({
            "key": "rsi",
            "label": f"RSI({rsi.get('period')})",
            "value": f"{rsi['value']:.0f} · {rsi.get('zone')}",
            "detail": f"Soglie {rsi.get('oversold')}/{rsi.get('overbought')} (tarate, non 70/30).",
            "state": "watch" if rsi.get("zone") in ("overbought", "oversold") else "neutral",
        })

    # ATR (volatility context).
    if technicals.get("atr") is not None:
        rows.append({
            "key": "atr",
            "label": "ATR(14)",
            "value": f"{technicals['atr']:.2f}"
            + (f" ({technicals['atr_pct']:.1f}%)" if technicals.get("atr_pct") is not None else ""),
            "detail": "Ampiezza media di oscillazione (volatilità realizzata).",
            "state": "neutral",
        })

    # Next catalyst.
    if next_event:
        rows.append({
            "key": "event",
            "label": "Prossimo evento",
            "value": next_event.get("title"),
            "detail": str(next_event.get("event_time")),
            "state": "watch",
        })

    return rows


# --- main entry ------------------------------------------------------
def run_decision_board(
    cfg: AppConfig,
    storage: Storage,
    options_provider: OptionsProvider,
    ai=None,
) -> dict[str, int]:
    db_cfg = dict(cfg.raw.get("decision_board", {}) or {})
    if not db_cfg.get("enabled", False):
        log.info("Decision board disabled in config — skipping.")
        return {"ok": 0, "failed": 0, "skipped": 1}

    macro_cfg = dict(db_cfg.get("macro", {}) or {})
    macro_days = int(macro_cfg.get("history_days", 365))
    br_cfg = dict(db_cfg.get("base_rate", {}) or {})
    horizons = list(br_cfg.get("horizons", [1, 3, 5]))
    min_sample = int(br_cfg.get("min_sample", 20))
    hist_days = int(cfg.indicators.get("history_days", 250))
    r = cfg.risk_free_rate
    today = datetime.now(timezone.utc).date()
    now_iso = datetime.now(timezone.utc).isoformat()

    instruments = list(db_cfg.get("instruments", []) or [])
    ok = failed = 0

    for inst in instruments:
        symbol = inst.get("symbol")
        try:
            iid = storage.get_instrument_id(symbol)
            rows = storage.get_price_history(iid, hist_days) if iid else []
            # storage returns newest-first; technicals/base-rate want ascending.
            asc = list(reversed(rows))
            closes = [float(b["close"]) for b in asc if b.get("close") is not None]
            highs = [float(b["high"]) for b in asc if b.get("high") is not None]
            lows = [float(b["low"]) for b in asc if b.get("low") is not None]

            rsi_cfg = dict(inst.get("rsi", {}) or {})
            technicals = tech.compute_technicals(
                highs, lows, closes,
                ma_periods=cfg.indicators.get("ma_periods", [20, 50, 200]),
                atr_period=int(cfg.indicators.get("atr_period", 14)),
                rsi_period=int(rsi_cfg.get("period", 14)),
                rsi_overbought=float(rsi_cfg.get("overbought", 80)),
                rsi_oversold=float(rsi_cfg.get("oversold", 40)),
                range_window=int(inst.get("range_window", 60)),
                round_step=inst.get("round_step"),
            ) if closes else {}

            base_rate = (
                streak_base_rate(closes, horizons=horizons, min_sample=min_sample).to_dict()
                if closes else {"status": "no_streak", "sample_size": 0, "caveat": STREAK_CAVEAT}
            )

            drivers = [
                _resolve_macro_driver(storage, drv, macro_days)
                for drv in inst.get("macro_drivers", [])
            ]

            proxy = inst.get("options_proxy") or symbol
            implied = implied_probabilities(
                options_provider, proxy, today=today,
                horizons_days=list(inst.get("implied_horizons_days", [1, 3, 30])),
                r=r,
            )

            up_events = storage.list_upcoming_events(25)
            events = _filter_events(up_events, list(inst.get("event_keywords", [])), 6)

            figures: list[dict] = []
            for fig in inst.get("figures", []):
                figures.extend(storage.list_statements_by_figure(fig, 5))

            confluence = build_confluence(
                drivers, technicals, base_rate, events[0] if events else None
            )

            # Synthesis (confluence read) — transparent lean + market divergence.
            synthesis = confluence_read(
                drivers=drivers,
                technicals=technicals,
                implied=implied,
                next_event=events[0] if events else None,
                weights=dict(inst.get("synthesis", {}).get("weights", {})),
            )

            board = {
                "symbol": symbol,
                "name": inst.get("name", symbol),
                "snapshot_at": now_iso,
                "last": technicals.get("last") if technicals else (closes[-1] if closes else None),
                "macro_drivers": drivers,
                "technicals": technicals,
                "base_rate": base_rate,
                "implied": implied,
                "events": events,
                "figures": figures,
                "confluence": confluence,
                "synthesis": synthesis,
            }

            # Optional NON-directional AI synthesis.
            if ai is not None:
                try:
                    from ..ai.decision import summarize_decision_board
                    summary = summarize_decision_board(
                        ai, model=cfg.briefing_model, board=board
                    )
                    if summary:
                        board["ai_summary"] = summary
                except Exception as exc:  # noqa: BLE001 — synthesis is optional
                    log.warning("Decision board AI synthesis failed for %s: %s", symbol, exc)

            storage.upsert_decision_board(symbol, board)
            ok += 1
            log.info(
                "Decision board built for %s (base rate n=%s status=%s)",
                symbol, base_rate.get("sample_size"), base_rate.get("status"),
            )
        except Exception as exc:  # noqa: BLE001 — isolate per-instrument
            failed += 1
            log.error("Decision board failed for %s: %s", symbol, exc)

    log.info("Decision board run done: %d ok, %d failed", ok, failed)
    return {"ok": ok, "failed": failed}

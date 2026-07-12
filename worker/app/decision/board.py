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

from datetime import date, datetime, timezone

from ..config import AppConfig
from ..logging_setup import get_logger
from ..base_rates import STREAK_CAVEAT, streak_base_rate
from ..providers.options import OptionsProvider
from ..storage import Storage
from .. import technicals as tech
from .implied import _atm_iv, _pick_expiry, implied_probabilities
from .synthesis import classify_macro_state, confluence_read
from . import fx_signals as fxs

log = get_logger("decision.board")

# Dual lens for single stocks — the same board, read two honest ways. Neither
# produces a directional forecast (CLAUDE.md §1, §5).
DUAL_LENSES = {
    "holding": ("Come HOLDING (anni): contano i FONDAMENTALI (qualità, valutazione, "
                "crescita, free cash flow). Il rumore di breve e i segnali tecnici "
                "contano poco."),
    "trade": ("Come TRADE (≤3 settimane): comanda l'EVENTO-UTILI e la notizia. I "
              "fondamentali sono contesto GIÀ prezzato."),
    "note": "Nessuna delle due lenti produce una previsione direzionale.",
}

# The 5 fixed sections, weighted 0..3 per instrument so every asset reads the same
# way but with the RIGHT emphasis (gold→macro, stocks→fundamentals/news, …).
# 0 = n/d, 1 = sfondo, 2 = secondario, 3 = primario. Config `sections` overrides.
_SECTION_KEYS = ("macro", "technical", "news", "cyclicality", "fundamentals")


def _instrument_costs(inst: dict, db_cfg: dict) -> dict:
    """Round-trip trading-cost estimate for the decision bench (config-driven)."""
    default = dict(db_cfg.get("costs_default", {}) or {})
    base = {"spread_bps": float(default.get("spread_bps", 5)),
            "commission": float(default.get("commission", 0))}
    override = inst.get("costs") or {}
    return {"spread_bps": float(override.get("spread_bps", base["spread_bps"])),
            "commission": float(override.get("commission", base["commission"]))}


def _section_emphasis(inst: dict) -> dict:
    base = ({"macro": 1, "technical": 2, "news": 3, "cyclicality": 1, "fundamentals": 3}
            if inst.get("fundamentals") else
            {"macro": 3, "technical": 2, "news": 2, "cyclicality": 2, "fundamentals": 0})
    override = inst.get("sections") or {}
    return {k: int(override.get(k, base[k])) for k in _SECTION_KEYS}


# --- macro driver resolution -----------------------------------------
def _direction(latest: float | None, prev: float | None) -> str:
    if latest is None or prev is None:
        return "flat"
    if latest > prev:
        return "up"
    if latest < prev:
        return "down"
    return "flat"


def _percentile(values: list[float], latest: float) -> float | None:
    """Fraction of the window at or below `latest` (0..1). The level's regime."""
    if not values:
        return None
    le = sum(1 for v in values if v <= latest)
    return le / len(values)


def _resolve_macro_driver(storage: Storage, drv: dict, days: int, regime: dict) -> dict:
    """Resolve a driver to its latest value, daily direction AND level/regime.

    The level/regime (percentile over `lookback_days`) lets the synthesis treat
    e.g. a high-but-falling real yield as a structural headwind, not "favorable".
    """
    sid = drv.get("id")
    source = (drv.get("source") or "fred").lower()
    lookback = int(regime.get("lookback_days", 252))
    values: list[float] = []
    latest = prev = None
    as_of = None

    if source == "price":
        iid = storage.get_instrument_id(sid)
        rows = storage.get_price_history(iid, max(lookback, 2)) if iid else []
        values = [float(r["close"]) for r in rows if r.get("close") is not None]
        if rows:
            as_of = rows[0].get("ts")
    else:  # fred (default)
        rows = storage.get_macro_series(sid, max(lookback, days))  # newest-first
        clean = [r for r in rows if r.get("value") is not None]
        values = [float(r["value"]) for r in clean]
        if clean:
            as_of = clean[0].get("obs_date")
    if values:
        latest = values[0]
    if len(values) > 1:
        prev = values[1]

    direction = _direction(latest, prev)
    change = (latest - prev) if (latest is not None and prev is not None) else None
    pctile = _percentile(values, latest) if latest is not None else None
    cls = classify_macro_state(
        drv.get("supportive_when"), direction, pctile,
        high_pct=float(regime.get("high_pct", 0.66)),
        low_pct=float(regime.get("low_pct", 0.34)),
        use_regime=bool(regime.get("use_regime", True)),
    )
    return {
        "id": sid,
        "label": drv.get("label", sid),
        "source": source,
        "value": latest,
        "prev": prev,
        "change": change,
        "direction": direction,
        "level_percentile": pctile,
        "regime": cls["regime"],
        "regime_class": cls["regime_class"],
        "move_class": cls["move_class"],
        "classification": cls["classification"],
        "state": cls["state"],
        "supportive_when": drv.get("supportive_when"),
        "interpretation": drv.get("interpretation"),
        "as_of": str(as_of) if as_of is not None else None,
    }


def _filter_events(events: list[dict], keywords: list[str], symbol: str, limit: int) -> list[dict]:
    """Keep events relevant to this instrument.

    Symbol-scoped events (e.g. earnings, symbols=[NVDA]) belong ONLY to their
    instrument; macro events (no symbols) match by keyword. This stops one
    stock's earnings from showing on another board.
    """
    kws = [k.lower() for k in keywords]
    out: list[dict] = []
    for e in events:
        syms = e.get("symbols") or []
        if syms:
            if symbol in syms:
                out.append(e)
        elif not kws or any(k in (e.get("title") or "").lower() for k in kws):
            out.append(e)
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


def _ev_date(s) -> date | None:
    try:
        return date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def _first_expiry_after(expiries: list[str], today: date, target_days: int) -> tuple[str, int] | None:
    """Smallest expiry with days-to-expiry >= target (the one that SPANS an event)."""
    best: tuple[str, int] | None = None
    for e in expiries:
        d = _ev_date(e)
        if d is None:
            continue
        dte = (d - today).days
        if dte >= target_days and (best is None or dte < best[1]):
            best = (e, dte)
    return best


# --- desk signals (instrument-driven: FX, index, …) ------------------
def _compute_fx_signals(cfg, storage, inst, implied, events, options_provider, today) -> dict:
    """Skew/RR (+percentile via macro_series), expected move on events, historical
    event behaviour, and COT positioning. All real (priced/measured) signals.

    Instrument-driven: the options proxy (`options_proxy`) and the COT contract
    (`positioning.market`) come from config — no ticker is hardcoded. Works for
    EUR/USD (FXE / EURO FX), Nasdaq (QQQ / NASDAQ MINI), and the next ones by
    config alone."""
    fxcfg = dict(inst.get("fx", {}) or {})
    proxy = inst.get("options_proxy") or inst["symbol"]
    r = cfg.risk_free_rate

    # --- skew / risk reversal per horizon ---
    skew: list[dict] = []
    spot = None
    expiries: list[str] = []
    try:
        spot = options_provider.get_spot(proxy)
        expiries = options_provider.list_expiries(proxy) if spot else []
    except Exception as exc:  # noqa: BLE001
        log.warning("FX skew: chains unavailable for %s: %s", proxy, exc)
    chain_cache: dict[str, list] = {}
    for target in fxcfg.get("rr_horizons_days", [1, 7, 30]):
        pick = _pick_expiry(expiries, today, target) if expiries else None
        if not pick:
            continue
        expiry, dte = pick
        if expiry not in chain_cache:
            try:
                chain_cache[expiry] = options_provider.fetch_chain(proxy, expiry)
            except Exception:  # noqa: BLE001
                chain_cache[expiry] = []
        T = max(dte, 0) / 365.0
        rr = (fxs.risk_reversal_from_quotes(chain_cache[expiry], spot, T, r)
              if (chain_cache[expiry] and spot and T > 0) else {"rr": None, "reliability": "low"})
        pct = None
        if rr.get("rr") is not None:
            sid = f"{proxy}_RR_{target}D"
            try:
                storage.upsert_macro_series([{ "series_id": sid, "obs_date": today.isoformat(),
                                               "value": rr["rr"], "source": "derived"}])
                hist = [float(x["value"]) for x in storage.get_macro_series(sid, 400)
                        if x.get("value") is not None]
                pct = _percentile(hist, rr["rr"]) if hist else None
            except Exception:  # noqa: BLE001
                pct = None
        skew.append({"target_days": target, "expiry": expiry, "days_to_expiry": dte,
                     "percentile": pct, "lean": fxs.rr_lean(rr.get("rr")), **rr})

    # --- expected move on the next events (IV term structure) ---
    # Use the option expiry that SPANS each event (incl. earnings, which can be
    # further out than the implied horizons). Seed with the implied horizons, then
    # add a spanning expiry per upcoming event (fetch + ATM IV) as needed.
    em_expiries: dict[str, dict] = {}
    for h in implied.get("horizons", []):
        if h.get("available") and h.get("atm_iv") and h.get("expiry"):
            em_expiries[h["expiry"]] = {"expiry": h["expiry"],
                                        "days_to_expiry": h["days_to_expiry"], "atm_iv": h["atm_iv"]}
    if expiries and spot:
        for ev in events:
            ed = _ev_date(ev.get("event_time"))
            if not ed or ed < today:
                continue
            dte_ev = (ed - today).days
            pick = _first_expiry_after(expiries, today, dte_ev)
            if not pick or pick[0] in em_expiries:
                continue
            exp, dte = pick
            if exp not in chain_cache:
                try:
                    chain_cache[exp] = options_provider.fetch_chain(proxy, exp)
                except Exception:  # noqa: BLE001
                    chain_cache[exp] = []
            T = max(dte, 0) / 365.0
            iv = _atm_iv(chain_cache[exp], spot, T, r) if (chain_cache[exp] and T > 0) else None
            if iv:
                em_expiries[exp] = {"expiry": exp, "days_to_expiry": dte, "atm_iv": iv}
    expected = fxs.expected_move_on_events(events, list(em_expiries.values()), today=today)

    # --- historical event behaviour (long history + past seeded events) ---
    behaviour = _fx_event_behaviour(cfg, inst, today, fxcfg)

    # --- COT positioning ---
    cot = _fx_cot(inst, fxcfg)

    result = {
        "underlying": proxy, "risk_reversal": skew, "expected_move_events": expected,
        "event_behaviour": behaviour, "cot": cot,
        "note": "Segnali reali (prezzati nelle opzioni o misurati dai dati), NON previsioni.",
    }
    # Honest flag: earnings requested but no dates available (yfinance gap).
    if inst.get("earnings") and behaviour.get("earnings_available") is False:
        result["earnings_note"] = (
            "Date earnings non disponibili (yfinance): expected-move e storico sugli "
            "earnings non calcolati per ora."
        )
    return result


def _fx_event_behaviour(cfg, inst, today, fxcfg) -> dict:
    try:
        from ..backtest.data import load_history
        from ..providers.prices import build_price_provider
        from ..providers.calendar.seeded_provider import SeededCalendarProvider
        pp = build_price_provider(cfg.providers.get("prices", "yfinance"))
        df = load_history(inst["symbol"], pp, days=int(fxcfg.get("history_days", 2000)))
    except Exception as exc:  # noqa: BLE001
        log.warning("FX event behaviour: history load failed: %s", exc)
        return {}
    dates = [d.date().isoformat() for d in df.index]
    closes = {d.date().isoformat(): float(c) for d, c in zip(df.index, df["close"])}
    seed = dict(cfg.raw.get("calendar", {}).get("seed", {}))
    evs = SeededCalendarProvider(seed).fetch_events(dates[0], today.isoformat()) if dates else []
    by_title: dict[str, list] = {}
    for e in evs:
        by_title.setdefault(e.title, []).append(e.event_time.date())
    follow = int(fxcfg.get("event_follow_days", 3))
    min_s = int(fxcfg.get("event_min_sample", 20))
    out = {}
    for title, eds in by_title.items():
        out[title] = fxs.event_behaviour(dates, closes, eds, follow_days=follow, min_sample=min_s)

    # Single-stock earnings: the dominant catalyst. Past earnings via yfinance.
    earnings_available = None
    if inst.get("earnings") and dates:
        earnings_available = False
        try:
            from ..ingestion.earnings import past_earnings
            from datetime import date as _date
            start = _date.fromisoformat(dates[0])
            eds = past_earnings(inst["symbol"], start, today)
        except Exception as exc:  # noqa: BLE001
            log.warning("Past earnings load failed for %s: %s", inst["symbol"], exc)
            eds = []
        if eds:
            earnings_available = True
            out[f"Earnings {inst.get('name', inst['symbol'])}"] = fxs.event_behaviour(
                dates, closes, eds, follow_days=follow, min_sample=min_s)

    return {"by_event": out, "earnings_available": earnings_available}


def _fx_cot(inst, fxcfg) -> dict | None:
    posc = dict(inst.get("positioning", {}) or {})
    if not posc:
        return None
    try:
        from ..providers.positioning import build_positioning_provider
        prov = build_positioning_provider(posc.get("provider", "cftc"))
        hist = prov.fetch_history(posc.get("market", "EURO FX"),
                                  lookback_weeks=int(posc.get("lookback_weeks", 156)),
                                  report=posc.get("report", "tff"))
    except Exception as exc:  # noqa: BLE001
        log.warning("COT fetch failed: %s", exc)
        return {"state": "n/d", "note": f"COT non disponibile: {exc}"}
    nets = [c.net for c in hist if c.net is not None]
    latest = nets[-1] if nets else None
    st = fxs.positioning_state(nets, latest)
    last = hist[-1] if hist else None
    market = posc.get("market", "")
    # Note is instrument-driven; `positioning.note` lets a config add a caveat
    # (e.g. for equity indices COT is a weaker signal than FX).
    base_note = (f"COT Leveraged Funds ({market}). Ritardo mar→ven; "
                 "contrarian solo agli estremi; swing, non intraday.")
    extra = posc.get("note")
    return {
        **st, "net": latest,
        "as_of": last.report_date.isoformat() if last else None,
        "lookback_weeks": int(posc.get("lookback_weeks", 156)),
        "note": f"{base_note} {extra}".strip() if extra else base_note,
    }


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
    regime_cfg = dict(macro_cfg.get("regime", {}) or {})
    br_cfg = dict(db_cfg.get("base_rate", {}) or {})
    horizons = list(br_cfg.get("horizons", [1, 3, 5]))
    min_sample = int(br_cfg.get("min_sample", 20))
    hist_days = int(cfg.indicators.get("history_days", 250))
    r = cfg.risk_free_rate
    today = datetime.now(timezone.utc).date()

    # Evidence-based lean weights (Part B): the LATEST explicit calibration, if any.
    # The gauge is labelled "calibrata al <date>"; non-significant factors → weight 0.
    calibration = None
    cal_weights: dict = {}
    try:
        calibration = storage.get_latest_calibration()
        cal_weights = (calibration or {}).get("weights", {}) or {}
    except Exception as exc:  # noqa: BLE001 — pre-0019 or none yet
        log.warning("No calibration available: %s", exc)
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
                _resolve_macro_driver(storage, drv, macro_days, regime_cfg)
                for drv in inst.get("macro_drivers", [])
            ]
            # Macro freshness: flag drivers whose last FRED obs is stale (feed lag).
            from .attribution import macro_freshness
            freshness = macro_freshness(
                drivers, today,
                int(macro_cfg.get("stale_after_business_days", 2)),
            )
            drivers = freshness["drivers"]   # annotated with as_of_date / stale / age

            proxy = inst.get("options_proxy") or symbol
            implied = implied_probabilities(
                options_provider, proxy, today=today,
                horizons_days=list(inst.get("implied_horizons_days", [1, 3, 30])),
                r=r,
            )

            up_events = storage.list_upcoming_events(25)
            events = _filter_events(up_events, list(inst.get("event_keywords", [])), symbol, 6)

            figures: list[dict] = []
            for fig in inst.get("figures", []):
                figures.extend(storage.list_statements_by_figure(fig, 5))

            confluence = build_confluence(
                drivers, technicals, base_rate, events[0] if events else None
            )

            # FX desk signals (EUR/USD): skew, expected move, event behaviour, COT.
            fx = None
            if inst.get("fx_signals"):
                try:
                    fx = _compute_fx_signals(cfg, storage, inst, implied, events, options_provider, today)
                except Exception as exc:  # noqa: BLE001 — optional enrichment
                    log.warning("FX signals failed for %s: %s", symbol, exc)

            # Single-stock: company fundamentals + fresh per-stock news (context).
            fundamentals = None
            stock_news_items = None
            if inst.get("fundamentals"):
                try:
                    from ..providers.fundamentals import build_fundamentals_provider
                    fundamentals = build_fundamentals_provider().fetch(symbol)
                except Exception as exc:  # noqa: BLE001 — optional enrichment
                    log.warning("Fundamentals failed for %s: %s", symbol, exc)
                try:
                    from .stock_news import recent_news
                    stock_news_items = recent_news(inst.get("name", symbol), symbol)
                except Exception as exc:  # noqa: BLE001
                    log.warning("Stock news failed for %s: %s", symbol, exc)

            # Synthesis (confluence read) — transparent lean + market divergence.
            # Evidence-based recomposition: calibrated weights override the config
            # ones for the tested lean factors (non-significant → 0). Explicit,
            # dated; still "conditions, not a probability".
            syn_weights = dict(inst.get("synthesis", {}).get("weights", {}))
            sym_cal = cal_weights.get(symbol) or {}
            for k, cw in sym_cal.items():
                if isinstance(cw, dict) and "weight" in cw:
                    syn_weights[k] = cw["weight"]
            synthesis = confluence_read(
                drivers=drivers,
                technicals=technicals,
                implied=implied,
                next_event=events[0] if events else None,
                weights=syn_weights,
                fx=fx,
            )
            if calibration and sym_cal:
                synthesis["calibration"] = {
                    "calibrated_at": calibration.get("calibrated_at"),
                    "period_start": calibration.get("period_start"),
                    "period_end": calibration.get("period_end"),
                    "weight_horizon": calibration.get("weight_horizon"),
                    "weights": sym_cal,
                    "note": ("Lancetta calibrata dall'evidenza: pesi ∝ IC out-of-sample dei "
                             "soli fattori significativi; i contrari sono azzerati (non invertiti); "
                             "i non significativi restano contesto a peso 0. Resta condizioni, non una previsione."),
                }

            # Event context (honest, never fused into the lean): what moved the
            # recent move, an imminent-event banner, and a dollar co-movement note.
            from .attribution import attribute_movement, dollar_note, event_risk_banner
            now_dt = datetime.now(timezone.utc)
            recent_return_pct = None
            if len(closes) >= 3:
                recent_return_pct = (closes[-1] / closes[-3] - 1.0) * 100.0
            attrib_days = int(db_cfg.get("attribution_lookback_days", 5))
            try:
                recent_events = _filter_events(
                    storage.list_recent_events(attrib_days, 25),
                    list(inst.get("event_keywords", [])), symbol, 4)
            except Exception as exc:  # noqa: BLE001
                log.warning("Recent events load failed for %s: %s", symbol, exc)
                recent_events = []
            attrib_news = stock_news_items
            if attrib_news is None:
                try:
                    from .stock_news import recent_news
                    attrib_news = recent_news(inst.get("name", symbol), symbol,
                                              days=attrib_days, limit=5)
                except Exception as exc:  # noqa: BLE001
                    log.warning("Attribution news failed for %s: %s", symbol, exc)
                    attrib_news = []
            attribution = attribute_movement(
                instrument_name=inst.get("name", symbol),
                recent_return_pct=recent_return_pct,
                news=attrib_news or [], past_events=recent_events, drivers=drivers,
                dollar_sensitivity=inst.get("dollar_sensitivity"),
            )
            event_risk = event_risk_banner(
                events, implied, symbol=symbol, now=now_dt,
                within_hours=float(db_cfg.get("event_risk_hours", 72)))
            dollar = dollar_note(drivers, inst.get("dollar_sensitivity"))

            # CICLICITÀ — seasonality over a long history (needs several years).
            # Honest by construction (n, min-sample, data-snooping caveat).
            seasonality = None
            try:
                from ..backtest.data import load_history
                from ..providers.prices import build_price_provider
                from .seasonality import compute_seasonality
                pp = build_price_provider(cfg.providers.get("prices", "yfinance"))
                sdf = load_history(symbol, pp, days=int(db_cfg.get("seasonality_history_days", 2600)))
                s_dates = [d.date().isoformat() for d in sdf.index]
                s_closes = [float(c) for c in sdf["close"]]
                seasonality = compute_seasonality(s_dates, s_closes)
            except Exception as exc:  # noqa: BLE001 — optional enrichment
                log.warning("Seasonality failed for %s: %s", symbol, exc)

            # Full-picture (single stocks): ALL states side by side, NEVER fused.
            full_picture = None
            if fundamentals:
                try:
                    from .full_picture import build_full_picture
                    nd = (((fundamentals.get("earnings") or {}).get("next_date")) or None)
                    d2e = (date.fromisoformat(nd) - today).days if nd else None
                    full_picture = build_full_picture(
                        fundamentals, synthesis, technicals, implied,
                        days_to_next_earnings=d2e)
                except Exception as exc:  # noqa: BLE001 — display aid only
                    log.warning("Full picture failed for %s: %s", symbol, exc)

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
                "fx_signals": fx,
                "fundamentals": fundamentals,
                "news": stock_news_items,
                "full_picture": full_picture,
                # Dual lens (single stocks): the SAME board reads differently as a
                # multi-year holding vs a <=3-week trade. Honest: neither is a forecast.
                "lenses": DUAL_LENSES if fundamentals else None,
                "board_note": inst.get("board_note"),
                "themes": list(inst.get("themes", []) or []),
                "seasonality": seasonality,
                "section_emphasis": _section_emphasis(inst),
                "fundamentals_note": inst.get("fundamentals_note"),
                "costs": _instrument_costs(inst, db_cfg),
                "macro_freshness": {k: v for k, v in freshness.items() if k != "drivers"},
                "attribution": attribution,
                "event_risk": event_risk,
                "dollar_note": dollar,
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

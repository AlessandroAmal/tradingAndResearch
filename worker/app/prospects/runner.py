"""Assemble the multi-horizon prospects grid per instrument and store it.

For each instrument:
  * CONDITIONAL (all horizons) — forward-return distribution given the current
    regime of the instrument's main driver(s): single (A) + pair (B), with n,
    effective n, 68/95 intervals (block bootstrap).
  * OPTIONS (≤ ~1y) — Breeden-Litzenberger risk-neutral density from the chain,
    per horizon, with a data-quality flag.
  * VALUATION (3y/5y, stocks/indices) — starting-valuation → forward return.

Each generated distribution is also written to the forward calibration registry
(prospect_forecasts) so reliability/coverage accumulate over time. Snapshot stored
as JSONB (like decision_boards). READ-ONLY, never an order; every number is either
market risk-neutral odds or a historical frequency with n.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from ..config import AppConfig
from ..logging_setup import get_logger
from ..storage import Storage
from . import bl, conditional as cond, valuation as val

log = get_logger("prospects.runner")

# horizon label -> trading days
HORIZONS = {"1s": 5, "1m": 21, "3m": 63, "6m": 126, "1a": 252, "5a": 1260}
OPTIONS_MAX_DAYS = 400          # BL only where an expiry within ~1y exists
VALUATION_HORIZONS = {"3a": 3, "5a": 5}
CAL = "Distribuzione di esiti, non una previsione puntuale."


def _asof_values(price_dates: list[str], macro_rows: list[dict]) -> list[float | None]:
    """Latest FRED value as-of each price date (causal, forward-filled)."""
    clean = sorted(((str(r.get("obs_date"))[:10], r.get("value")) for r in macro_rows
                    if r.get("value") is not None), key=lambda x: x[0])
    out: list[float | None] = []
    i, cur = 0, None
    for d in price_dates:
        while i < len(clean) and clean[i][0] <= d:
            cur = float(clean[i][1]); i += 1
        out.append(cur)
    return out


def _conditional_block(closes, dates, drivers_regimes, min_effective) -> dict:
    """Single (A) + pair (B) conditional distributions at every horizon, using each
    driver's CURRENT regime (its label on the latest date)."""
    current = {d: labels[-1] for d, labels in drivers_regimes.items() if labels and labels[-1]}
    names = list(current)
    out: dict = {"current_regimes": current, "by_horizon": {}}
    for label, h in HORIZONS.items():
        single = {}
        for d in names:                                   # A: one driver each
            single[d] = cond.conditional_distribution(
                closes, h, drivers_regimes, {d: current[d]}, min_effective=min_effective)
        pair = None
        if len(names) >= 2:                               # B: the two main drivers
            pair = cond.conditional_distribution(
                closes, h, drivers_regimes, {names[0]: current[names[0]], names[1]: current[names[1]]},
                min_effective=min_effective)
        out["by_horizon"][label] = {"single": single, "pair": pair}
    return out


# Plausibility ceiling for |median return| per horizon — a risk-neutral median
# is ≈ the forward (near 0), so anything larger signals a UNIT bug (proxy≠spot).
SANITY_MAX_MEDIAN = {"1s": 0.30, "1m": 0.60, "3m": 1.00, "6m": 1.50, "1a": 2.0}


def _options_block(cfg, options_provider, inst, today, instrument_spot) -> dict:
    """BL risk-neutral density at the nearest expiry to each target horizon (≤1y),
    expressed in RETURNS vs the proxy spot (so it applies to the instrument spot,
    whatever the proxy scale). Each horizon carries a sanity check."""
    proxy = inst.get("options_proxy") or inst["symbol"]
    r = cfg.risk_free_rate
    caps = dict((cfg.prospects.get("sanity_max_median") or {}))
    out: dict = {"proxy": proxy, "by_horizon": {}}
    try:
        spot = options_provider.get_spot(proxy)          # PROXY spot (e.g. GLD ~400)
        expiries = options_provider.list_expiries(proxy) if spot else []
    except Exception as exc:  # noqa: BLE001
        log.warning("Prospects options: chain unavailable for %s: %s", proxy, exc)
        return out
    if not spot or not expiries:
        return out
    out["proxy_spot"] = spot
    dted = []
    for e in expiries:
        try:
            dte = (date.fromisoformat(e[:10]) - today).days
            if 0 < dte <= OPTIONS_MAX_DAYS:
                dted.append((e, dte))
        except ValueError:
            continue
    chain_cache: dict[str, list] = {}
    for label, h in HORIZONS.items():
        if h > OPTIONS_MAX_DAYS or not dted:
            continue
        exp, dte = min(dted, key=lambda x: abs(x[1] - h))
        if exp not in chain_cache:
            try:
                chain_cache[exp] = options_provider.fetch_chain(proxy, exp)
            except Exception:  # noqa: BLE001
                chain_cache[exp] = []
        quotes = chain_cache[exp]
        if not quotes:
            continue
        T = max(dte, 1) / 365.0
        dens = bl.risk_neutral_density(quotes, spot, T, r)     # in PROXY units
        s = bl.return_summary(dens)                            # -> RETURNS vs proxy spot
        s["expiry_used"] = exp
        s["days_to_expiry"] = dte
        s["horizon_days"] = h
        # Sanity: a risk-neutral median return must be near 0; a huge value means
        # a unit mismatch slipped through. Refuse to show it, with the details.
        cap = float(caps.get(label, SANITY_MAX_MEDIAN.get(label, 2.0)))
        med = s.get("median_ret")
        if s.get("available") and med is not None and abs(med) > cap:
            s = {"available": False, "implausible": True, "median_ret": med,
                 "expiry_used": exp, "days_to_expiry": dte, "horizon_days": h,
                 "detail": {"instrument_spot": instrument_spot, "proxy_spot": spot,
                            "ratio": (instrument_spot / spot) if (instrument_spot and spot) else None},
                 "note": "risultato implausibile — controllo di coerenza fallito (unità proxy/strumento)"}
        out["by_horizon"][label] = s
    return out


def _register_forecasts(storage, symbol, cond_block, options_block, spot, today, combined_block=None):
    """Log declared distributions to the forward registry (best-effort)."""
    rows = []
    for label, h in HORIZONS.items():
        target = (today + timedelta(days=int(h * 1.4))).isoformat()   # ~calendar days
        cmb = (combined_block or {}).get("by_horizon", {}).get(label)
        if cmb and cmb.get("available"):
            rows.append({"symbol": symbol, "horizon_days": h, "method": "combined",
                         "median": cmb.get("median"), "p16": cmb.get("p16"), "p84": cmb.get("p84"),
                         "p2_5": cmb.get("p2_5"), "p97_5": cmb.get("p97_5"),
                         "entry_price": spot, "target_date": target})
        pair = (cond_block.get("by_horizon", {}).get(label) or {}).get("pair")
        if pair and pair.get("sufficient"):
            rows.append({"symbol": symbol, "horizon_days": h, "method": "conditional",
                         "median": pair.get("median"), "p16": pair.get("p16"), "p84": pair.get("p84"),
                         "p2_5": pair.get("p2_5"), "p97_5": pair.get("p97_5"),
                         "entry_price": spot, "target_date": target})
        opt_s = options_block.get("by_horizon", {}).get(label)
        # options are ALREADY in returns (vs proxy spot) -> store directly, no /spot.
        if opt_s and opt_s.get("available") and opt_s.get("quality", {}).get("reliable"):
            rows.append({"symbol": symbol, "horizon_days": h, "method": "options",
                         "median": opt_s.get("median_ret"), "p16": opt_s.get("p16_ret"),
                         "p84": opt_s.get("p84_ret"), "p2_5": opt_s.get("p2_5_ret"),
                         "p97_5": opt_s.get("p97_5_ret"),
                         "entry_price": spot, "target_date": target})
    for row in rows:
        try:
            storage.insert_prospect_forecast(row)
        except Exception as exc:  # noqa: BLE001 — needs 0020
            log.warning("prospect_forecast insert failed (apply 0020?): %s", exc)
            break


# horizon label -> the calibration horizon (days) whose factor IC drives the tilt.
# Factor calibration only reaches ~21d, so longer horizons get NO tilt (honest).
_TILT_HORIZON_DAYS = {"1s": "5", "1m": "21", "3m": "21", "6m": None, "1a": None}


def _combined_block(cond_block, options_block, cov_by_h, factor_ic) -> dict:
    """Per-horizon COMBINED distribution from options + conditional, with weights
    from the track record and a bounded tilt from significant-IC factors. Adopts
    the combined only where the (bootstrapped) score beats the best component."""
    from . import combine as CB
    out: dict = {"by_horizon": {}}
    for label, h in HORIZONS.items():
        opt = options_block.get("by_horizon", {}).get(label)
        pair = (cond_block.get("by_horizon", {}).get(label) or {}).get("pair")
        components: dict = {}
        if opt and opt.get("available") and (opt.get("quality") or {}).get("reliable"):
            components["options"] = {"median": opt.get("median_ret"), "p16": opt.get("p16_ret"), "p84": opt.get("p84_ret")}
        if pair and pair.get("sufficient"):
            components["conditional"] = {"median": pair.get("median"), "p16": pair.get("p16"), "p84": pair.get("p84")}
        if not components:
            out["by_horizon"][label] = {"available": False}
            continue
        # per-component calibration signal: conditional coverage_95 (retrospective);
        # options has no historical-chain track record -> no score (equal fallback).
        cal = {}
        if "conditional" in components:
            cal["conditional"] = {"coverage_95": (cov_by_h.get(label) or {}).get("coverage_95")}
        if "options" in components:
            cal["options"] = {}
        weights = CB.component_weights(cal) if len(components) > 1 else {list(components)[0]: 1.0}
        # tilt from significant-IC factors at (roughly) this horizon
        tilt = {"shift": 0.0, "factors_used": []}
        thd = _TILT_HORIZON_DAYS.get(label)
        if thd and factor_ic:
            fl = [{"key": k, "ic": (v.get(thd) or {}).get("ic"),
                   "significant": (v.get(thd) or {}).get("significant"),
                   "contrary": ((v.get(thd) or {}).get("ic") or 0) < 0 and (v.get(thd) or {}).get("significant")}
                  for k, v in factor_ic.items() if isinstance(v, dict)]
            tilt = CB.factor_tilt(fl)
        combined = CB.combine(components, weights, tilt=tilt["shift"])
        if combined.get("available"):
            combined["tilt_factors"] = tilt["factors_used"]
            combined["components_available"] = list(components)
            # OOS adoption is bootstrapped from coverage until the forward registry
            # accumulates; the combined is shown, marked not-yet-validated.
            combined["adoption"] = CB.adopt_combined(None, None, None)
        out["by_horizon"][label] = combined
    return out


def run_prospects(cfg: AppConfig, storage: Storage, options_provider,
                  price_provider, *, progress=None) -> dict[str, int]:
    db_cfg = dict(cfg.raw.get("decision_board", {}) or {})
    instruments = list(db_cfg.get("instruments", []) or [])
    pcfg = dict(cfg.raw.get("prospects", {}) or {})
    min_eff = int(pcfg.get("min_effective", 5))
    hist_days = int(pcfg.get("history_days", 5475))
    today = datetime.now(timezone.utc).date()
    from ..backtest.data import load_history

    # Track-record inputs for the combined: latest retrospective coverage (per
    # symbol×horizon) and the latest indicator calibration (factor IC), if any.
    try:
        retro = storage.get_latest_prospect_calibration("retrospective") or {}
        cov_all = retro.get("results", {}) or {}
    except Exception:  # noqa: BLE001
        cov_all = {}
    try:
        indi = storage.get_latest_calibration() or {}
        ic_all = indi.get("results", {}) or {}
    except Exception:  # noqa: BLE001
        ic_all = {}

    ok = failed = 0
    total = len(instruments)
    for idx, inst in enumerate(instruments):
        symbol = inst.get("symbol")
        if progress:
            progress(idx, total, symbol)
        try:
            df = load_history(symbol, price_provider, days=hist_days)
            dates = [d.date().isoformat() for d in df.index]
            closes = [float(c) for c in df["close"]]
            spot = closes[-1] if closes else None

            # conditioning drivers: the instrument's FRED macro drivers (up to 2)
            regimes: dict[str, list] = {}
            for drv in inst.get("macro_drivers", [])[:2]:
                if (drv.get("source") or "fred").lower() != "fred":
                    continue
                vals = _asof_values(dates, storage.get_macro_series(drv.get("id"), 6000))
                regimes[drv.get("label", drv.get("id"))] = cond.tercile_regime(vals)
            cond_block = _conditional_block(closes, dates, regimes, min_eff)

            options_block = _options_block(cfg, options_provider, inst, today, spot)

            valuation_block = None
            if inst.get("fundamentals") or inst.get("asset_class") in ("equity", "index", "etf"):
                # valuation history is not stored long-term -> declare the limit
                valuation_block = {"available": False,
                                   "note": "Relazione valutazione→rendimento non disponibile: "
                                           "storico valutazioni non conservato. Placeholder onesto."}

            combined_block = _combined_block(
                cond_block, options_block, cov_all.get(symbol, {}), ic_all.get(symbol, {}))

            # Multi-year EPISODES (rare patterns, read one-by-one, no % under n<10).
            from . import episodes as EP
            episodes_block = {
                "drawdown": EP.drawdown_episodes(dates, closes, threshold=0.20, forward=252),
            }
            # Bull-year run applies to equities/indices (the canonical "Nth year of a
            # bull market" case). Skip only FX/commodity where it's meaningless.
            sym_u = (symbol or "").upper()
            is_fx_comm = "=X" in sym_u or "=F" in sym_u
            if not is_fx_comm:
                episodes_block["bull_year"] = EP.bull_year_episodes(dates, closes, nth=3)

            snapshot = {
                "symbol": symbol, "name": inst.get("name", symbol),
                "as_of": datetime.now(timezone.utc).isoformat(), "spot": spot,
                "horizons": list(HORIZONS), "conditional": cond_block,
                "options": options_block, "valuation": valuation_block,
                "combined": combined_block, "episodes": episodes_block,
                "labels": {
                    "distribution": CAL,
                    "options": "Le probabilità da opzioni sono risk-neutral (odds di mercato), non del mondo reale.",
                    "conditional": "Storico condizionato = frequenza passata con n, non garanzia.",
                },
            }
            storage.upsert_prospects(symbol, snapshot)
            _register_forecasts(storage, symbol, cond_block, options_block, spot, today, combined_block)
            ok += 1
        except Exception as exc:  # noqa: BLE001 — isolate per instrument
            failed += 1
            log.error("Prospects failed for %s: %s", symbol, exc)
    log.info("Prospects: %d ok, %d failed", ok, failed)
    return {"ok": ok, "failed": failed}

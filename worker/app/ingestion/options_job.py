"""Options desk ingestion (M5).

For each options-capable underlying (universe equities/ETFs, holdings, and
macro proxies), fetch the first N expiries and the strikes around ATM,
RECALCULATE IV + Greeks per contract (Yahoo's IV is ignored), and upsert into
options_chains. Then, per holding, build default hedge PROPOSALS (protective
put + collar) with cost/floor/breakeven/%-covered and store them.

READ-ONLY: proposals only — nothing is ordered. Per-underlying isolation,
retry/backoff, graceful skip for underlyings without options.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from .. import options as opt
from ..config import AppConfig
from ..logging_setup import get_logger
from ..providers.options import OptionsProvider
from ..storage import Storage
from .retry import with_retry

log = get_logger("ingestion.options")


def _years_to(expiry: str, today: date) -> float:
    d = date.fromisoformat(expiry[:10])
    return max((d - today).days, 0) / 365.0


def _mid(q) -> float | None:
    if q.bid and q.ask and q.bid > 0 and q.ask > 0:
        return (q.bid + q.ask) / 2.0
    return q.last if (q.last and q.last > 0) else None


def _resolve_underlyings(cfg: AppConfig) -> tuple[list[str], dict[str, str]]:
    """Return (underlyings to fetch, holding_symbol -> underlying map).

    Macro symbols map to a proxy ETF; symbols without options/proxy are
    skipped (logged by the caller when fetched).
    """
    proxies = cfg.macro_proxies
    underlyings: list[str] = []
    holding_map: dict[str, str] = {}

    def add(u: str):
        if u and u not in underlyings:
            underlyings.append(u)

    # Universe: equities/ETFs directly; macro via proxy.
    for inst in cfg.universe:
        if inst.symbol in proxies:
            add(proxies[inst.symbol])
        elif inst.asset_class in ("equity", "etf"):
            add(inst.symbol)

    # Holdings: map each to a tradeable options underlying when possible.
    for h in cfg.holdings:
        u = None
        if h.symbol in proxies:
            u = proxies[h.symbol]
        elif (h.asset_class or "") in ("equity", "etf"):
            u = h.symbol
        if u:
            add(u)
            holding_map[h.symbol] = u
    return underlyings, holding_map


def run_options_ingestion(
    cfg: AppConfig, storage: Storage, provider: OptionsProvider
) -> dict[str, int]:
    today = datetime.now(timezone.utc).date()
    r = cfg.risk_free_rate
    n_exp = cfg.options_expiries_count
    window = cfg.options_strikes_window_pct

    underlyings, holding_map = _resolve_underlyings(cfg)
    # Cache fetched chains: (underlying, expiry) -> (spot, [quotes])
    chains: dict[tuple[str, str], tuple[float, list]] = {}
    spots: dict[str, float] = {}
    rows: list[dict] = []
    ok = skipped = failed = 0

    for u in underlyings:
        try:
            expiries = with_retry(lambda u=u: provider.list_expiries(u), label=f"expiries({u})")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            log.error("Options expiries failed for %s: %s", u, exc)
            continue
        if not expiries:
            skipped += 1
            log.info("No options for %s — skipping (FX/crypto/no proxy)", u)
            continue

        spot = provider.get_spot(u)
        if not spot:
            skipped += 1
            log.warning("No spot for %s — skipping", u)
            continue
        spots[u] = spot

        for expiry in expiries[:n_exp]:
            try:
                quotes = with_retry(
                    lambda u=u, e=expiry: provider.fetch_chain(u, e),
                    label=f"chain({u},{expiry})",
                )
            except Exception as exc:  # noqa: BLE001
                failed += 1
                log.error("Options chain failed for %s %s: %s", u, expiry, exc)
                continue

            chains[(u, expiry)] = (spot, quotes)
            T = _years_to(expiry, today)
            lo, hi = spot * (1 - window), spot * (1 + window)
            for q in quotes:
                if q.strike < lo or q.strike > hi:
                    continue
                mid = _mid(q)
                iv = opt.implied_vol(q.option_type, mid, spot, q.strike, T, r) if mid else None
                g = opt.greeks(q.option_type, spot, q.strike, T, r, iv) if iv else {}
                rows.append(
                    {
                        "underlying": u,
                        "expiry": expiry,
                        "strike": q.strike,
                        "option_type": q.option_type,
                        "bid": q.bid,
                        "ask": q.ask,
                        "last": q.last,
                        "mid": mid,
                        "volume": q.volume,
                        "open_interest": q.open_interest,
                        "implied_vol": iv,
                        "delta": g.get("delta"),
                        "gamma": g.get("gamma"),
                        "theta": g.get("theta"),
                        "vega": g.get("vega"),
                        "rho": g.get("rho"),
                        "source": provider.name,
                    }
                )
            ok += 1

    try:
        storage.upsert_options_chain(rows)
    except Exception as exc:  # noqa: BLE001
        log.error("Storing options chains failed: %s", exc)
        failed += 1

    proposals = _build_hedge_proposals(cfg, holding_map, chains, spots, today)
    try:
        storage.replace_hedge_proposals(proposals)
    except Exception as exc:  # noqa: BLE001
        log.error("Storing hedge proposals failed: %s", exc)
        failed += 1

    log.info(
        "Options ingestion done: %d chains, %d contracts, %d proposals, "
        "%d skipped, %d failed",
        ok, len(rows), len(proposals), skipped, failed,
    )
    return {"ok": ok, "contracts": len(rows), "proposals": len(proposals),
            "skipped": skipped, "failed": failed}


def _nearest(strikes: list[float], target: float) -> float | None:
    return min(strikes, key=lambda s: abs(s - target)) if strikes else None


def _legs_to_json(legs) -> list[dict]:
    return [
        {"kind": l.kind, "side": l.side, "strike": l.strike, "premium": l.premium, "qty": l.qty}
        for l in legs
    ]


def _build_hedge_proposals(cfg, holding_map, chains, spots, today) -> list[dict]:
    hedge = cfg.options_hedge
    put_otm = float(hedge.get("put_otm_pct", 0.05))
    call_otm = float(hedge.get("call_otm_pct", 0.05))
    min_days = int(hedge.get("min_days", 30))

    # holding qty by symbol (for % covered).
    qty_by_symbol = {h.symbol: float(h.quantity or 0) for h in cfg.holdings}
    proposals: list[dict] = []

    for symbol, u in holding_map.items():
        spot = spots.get(u)
        if not spot:
            continue
        # First fetched expiry that is at least min_days out.
        exp = _first_expiry(chains, u, today, min_days)
        if not exp:
            continue
        _, quotes = chains[(u, exp)]
        puts = {q.strike: _mid(q) for q in quotes if q.option_type == "put"}
        calls = {q.strike: _mid(q) for q in quotes if q.option_type == "call"}

        put_strike = _nearest([k for k, v in puts.items() if v], spot * (1 - put_otm))
        if put_strike is None:
            continue
        put_prem = puts[put_strike]

        qty = qty_by_symbol.get(symbol, 0.0)
        qty_for_calc = qty if qty > 0 else 100.0   # illustrative 1 contract
        pct_covered = 100.0 if qty > 0 else None

        # Protective put
        m = opt.protective_put(spot, put_strike, put_prem, qty=qty_for_calc)
        proposals.append(_proposal(symbol, u, "protective_put", exp, spot, m, put_strike,
                                   None, pct_covered, qty, "Floor = put strike less premium."))

        # Collar (add a short call ~call_otm OTM)
        call_strike = _nearest([k for k, v in calls.items() if v], spot * (1 + call_otm))
        if call_strike is not None:
            call_prem = calls[call_strike]
            mc = opt.collar(spot, put_strike, put_prem, call_strike, call_prem, qty=qty_for_calc)
            proposals.append(_proposal(symbol, u, "collar", exp, spot, mc, put_strike,
                                       call_strike, pct_covered, qty,
                                       "Downside floored, upside capped at the short call."))
    return proposals


def _first_expiry(chains, underlying, today, min_days):
    candidates = sorted(e for (uu, e) in chains if uu == underlying)
    for e in candidates:
        if (date.fromisoformat(e[:10]) - today).days >= min_days:
            return e
    return candidates[0] if candidates else None


def _proposal(symbol, underlying, kind, expiry, spot, m, put_strike, cap_strike,
              pct_covered, qty, note) -> dict:
    return {
        "symbol": symbol,
        "underlying": underlying,
        "kind": kind,
        "expiry": expiry,
        "legs": _legs_to_json(m.legs),
        "spot": spot,
        "cost": m.net_cost,
        "floor": put_strike,          # protected price floor
        "breakeven": m.breakeven,
        "max_gain": cap_strike,       # collar cap price (None for protective put)
        "pct_covered": pct_covered,
        "note": note + ("" if qty > 0 else " (qty 0 — illustrative 1 contract)"),
    }

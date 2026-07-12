"""Pre-trade gate — wires the discipline into a checklist. PURE & TESTED.

Before a position is recorded, this VALIDATES the numbers against the user's own
configured rules and surfaces clear WARNINGS — it never blocks, never sends an
order, and never gives a directional probability (CLAUDE.md: read-only, honest
about edge). Computing a size is a calculator, not an order.

It reuses the audited M6 risk math (`app.risk`) so risk/heat/R:R use the correct
point value (contract_multiplier). Warnings produced:
  * risk-per-trade over the limit
  * resulting portfolio heat over the limit
  * concurrent positions over the limit
  * reward/risk below the configured minimum
  * an imminent HIGH-impact event on the instrument (size-down / wait)
  * trade against the decision-board lean (INFO note, never a veto)

Discipline guards (all OPT-IN — they only fire when their input is supplied, so
existing callers/tests are unaffected):
  * STOP mandatory — missing stop BLOCKS sizing/registration ('block').
  * stop too tight vs ATR — inside normal noise, premature-stop risk.
  * budget caps day/week/month — committed risk over the cap (warn or block).
  * COUNTERTREND — short in an uptrend / long in a downtrend: WARNS and cites the
    user's own rule. It never *implements* the "buy strength, aim down" rule.
  * re-entry in the same losing direction; adding to a loser; thesis required.

Honest by construction: the gate validates DISCIPLINE and RISK, not direction. It
produces NO directional probability and NO score telling you which way to bet.

Tested in `worker/tests/test_gate.py`.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from . import risk as risk_math

GATE_CAVEAT = "Il gate valida disciplina e rischio, NON la direzione."

# The user's own rules, quoted verbatim in the guard messages (their words are
# the most effective nudge — see the brief). Never a directional instruction.
RULE_COUNTERTREND_SHORT = (
    "Stai puntando contro il trend (SHORT con prezzo sopra le medie chiave). "
    "Regola tua: non puntare al ribasso solo perché «il prezzo è alto». "
    "Così hai perso 2500€ sull'oro."
)
RULE_COUNTERTREND_LONG = (
    "Stai comprando in un chiaro downtrend (LONG con prezzo sotto le medie chiave). "
    "Regola tua: non entrare solo perché «il prezzo è basso rispetto a cosa?»."
)
RULE_REENTRY = (
    "Stai rientrando nella stessa direzione che ha appena perso — è il pattern "
    "dell'oro (6 volte di fila)."
)
RULE_ADDING = "Stai aumentando su un perdente: una posizione aperta nello stesso verso è già in perdita."
RULE_THESIS = (
    "Serve una tesi (regola 2.1): una ragione valida e una direzione attesa nel "
    "periodo — non «è alto/basso rispetto a cosa?»."
)


@dataclass(frozen=True)
class GateWarning:
    code: str
    severity: str        # 'block' (mandatory) | 'warn' (rule breached) | 'info' (note)
    message: str


# --- discipline guards (pure; each returns a message or None) ---------
def trend_conflict(side: str, technicals: Mapping | None) -> str | None:
    """Countertrend INTERCEPTOR (a warning, never the rule itself).

    Short in a clear uptrend (price above the key MAs) or long in a clear
    downtrend → return the user's rule text; otherwise None. Neutral/mixed → None.
    """
    if not technicals:
        return None
    mas = {m.get("period"): m for m in technicals.get("ma", [])}
    above200 = (mas.get(200) or {}).get("above")
    above50 = (mas.get(50) or {}).get("above")
    if above200 is None and above50 is None:
        return None
    uptrend = above200 is True and above50 is not False
    downtrend = above200 is False and above50 is not True
    if side == "short" and uptrend:
        return RULE_COUNTERTREND_SHORT
    if side == "long" and downtrend:
        return RULE_COUNTERTREND_LONG
    return None


def _has_losing_same_dir(side: str, trades: Sequence[Mapping]) -> bool:
    """True if any trade in `trades` is the SAME side and closed/open at a loss."""
    for t in trades or ():
        if t.get("side") == side and (t.get("pnl") or 0) < 0:
            return True
    return False


# --- kill-switch helpers (pre-mortem rules the user set when lucid) ---
def consecutive_losses(closed_trades: Sequence[Mapping]) -> int:
    """Trailing run of losing closed trades (list NEWEST-first)."""
    run = 0
    for t in closed_trades or ():
        pnl = t.get("pnl") if t.get("pnl") is not None else t.get("realized_pnl")
        if pnl is not None and pnl < 0:
            run += 1
        else:
            break
    return run


def cooldown_hit(recent_stops: Sequence[Mapping], symbol: str, side: str,
                 now: datetime, cooldown_hours: float) -> dict | None:
    """A stop TAKEN on the same symbol+direction within the cooldown window → the
    anti-revenge rule. `recent_stops` items: {symbol, side, closed_at}."""
    if cooldown_hours <= 0:
        return None
    for t in recent_stops or ():
        if t.get("symbol") != symbol or t.get("side") != side:
            continue
        when = _parse_dt(t.get("closed_at"))
        if when is None:
            continue
        hours = (now - when).total_seconds() / 3600.0
        if 0 <= hours <= cooldown_hours:
            return {"hours_ago": hours, "cooldown_hours": cooldown_hours}
    return None


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return dt
    except ValueError:
        return None


def imminent_event(
    events: Sequence[dict],
    *,
    symbol: str,
    now: datetime,
    within_hours: float,
    importances: tuple[str, ...] = ("high",),
) -> dict | None:
    """Nearest HIGH-impact event affecting `symbol` within the window, or None.

    An event with no `symbols` is treated as macro (affects everything, e.g. FOMC).
    """
    horizon = now + timedelta(hours=within_hours)
    best: tuple[datetime, dict] | None = None
    for e in events:
        if (e.get("importance") or "").lower() not in importances:
            continue
        syms = e.get("symbols") or []
        if syms and symbol not in syms:
            continue
        when = _parse_dt(e.get("event_time"))
        if when is None or when < now or when > horizon:
            continue
        if best is None or when < best[0]:
            best = (when, e)
    return best[1] if best else None


def evaluate_gate(
    *,
    symbol: str,
    side: str,
    entry: float,
    stop: float | None,
    target: float | None,
    size: float,
    multiplier: float = 1.0,
    account_size: float,
    max_risk_per_trade_pct: float,
    max_portfolio_heat_pct: float,
    max_concurrent_positions: int,
    rr_min: float = 1.5,
    existing_heat_pct: float = 0.0,
    open_count: int = 0,
    thesis: str | None = None,
    alignment: str | None = None,       # 'aligned' | 'contrarian' | 'na'
    lean_direction: str | None = None,  # from the decision board, for display
    events: Sequence[dict] = (),
    now: datetime | None = None,
    event_warn_hours: float = 48.0,
    # --- discipline guards (opt-in; unset = old behaviour) ---
    require_thesis: bool = False,
    atr: float | None = None,
    stop_atr_min_multiple: float = 1.5,
    technicals: Mapping | None = None,
    recent_closed_same_symbol: Sequence[Mapping] = (),
    open_same_symbol: Sequence[Mapping] = (),
    budget_caps: Mapping | None = None,   # {"day":{"max":100,"mode":"warn"}, ...}
    budget_used: Mapping | None = None,   # {"day":40,"week":120,"month":250} currency
    # --- kill-switch (pre-mortem rules the user set when lucid) ---
    killswitch: Mapping | None = None,    # {enabled, max_consecutive_losses, cooldown_hours, until}
    consecutive_loss_count: int = 0,      # trailing losses in the CURRENT scope (real|paper)
    cooldown: Mapping | None = None,      # {hours_ago, cooldown_hours} if a stop was just taken same sym+dir
) -> dict:
    """Validate a prospective trade. Returns metrics + warnings + a journal draft.
    Warnings inform; only mandatory-stop and block-mode budget caps are blocking."""
    risk_amount = risk_math.open_risk(entry, stop, size, multiplier)
    risk_pct = risk_math.pct_of_account(risk_amount, account_size)
    rr = risk_math.r_multiple_potential(entry, stop, target)
    resulting_heat_pct = (existing_heat_pct or 0.0) + (risk_pct or 0.0)
    n_concurrent = open_count + 1
    stop_distance = abs(entry - stop) if stop is not None else None

    warnings: list[GateWarning] = []

    # STOP LOSS MANDATORY — no sizing / no registration without it (blocks).
    if stop is None:
        warnings.append(GateWarning(
            "stop_missing", "block",
            "Stop loss obbligatorio: senza stop non si dimensiona né si registra il trade.",
        ))

    if risk_pct is not None and risk_pct > max_risk_per_trade_pct:
        warnings.append(GateWarning(
            "risk_per_trade", "warn",
            f"Rischio per trade {risk_pct:.2f}% oltre il limite {max_risk_per_trade_pct:.2f}%.",
        ))
    if resulting_heat_pct > max_portfolio_heat_pct:
        warnings.append(GateWarning(
            "heat", "warn",
            f"Heat risultante {resulting_heat_pct:.2f}% oltre il limite {max_portfolio_heat_pct:.2f}%.",
        ))
    if n_concurrent > max_concurrent_positions:
        warnings.append(GateWarning(
            "concurrent", "warn",
            f"{n_concurrent} posizioni concorrenti oltre il limite {max_concurrent_positions}.",
        ))
    if rr is not None and rr < rr_min:
        warnings.append(GateWarning(
            "rr_low", "warn",
            f"R/R {rr:.2f} sotto la soglia {rr_min:.2f}.",
        ))
    elif rr is None:
        warnings.append(GateWarning(
            "rr_missing", "info",
            "R/R non calcolabile (manca stop o target).",
        ))

    ev = imminent_event(events, symbol=symbol, now=now or datetime.now().astimezone(),
                        within_hours=event_warn_hours) if events else None
    if ev:
        warnings.append(GateWarning(
            "event_risk", "warn",
            f"Rischio evento: «{ev.get('title')}» ({str(ev.get('event_time'))[:16]}) "
            f"entro {event_warn_hours:.0f}h — valuta size ridotta o attesa.",
        ))

    if alignment == "contrarian":
        warnings.append(GateWarning(
            "contrarian", "info",
            f"Trade CONTRO la lettura macro{f' ({lean_direction})' if lean_direction else ''}: "
            "non è un divieto, ma sii consapevole di andare contro la marea.",
        ))

    # SIZING WITH ROOM — stop must clear normal volatility (k×ATR).
    if stop_distance is not None and atr and atr > 0 and stop_atr_min_multiple > 0:
        floor = stop_atr_min_multiple * atr
        if stop_distance < floor:
            warnings.append(GateWarning(
                "stop_too_tight", "warn",
                f"Stop a {stop_distance:.2f} < {stop_atr_min_multiple:g}×ATR ({floor:.2f}): "
                "dentro il rumore normale — rischi la chiusura prematura prima che il "
                "trade possa svilupparsi. Dai più margine o riduci la size.",
            ))

    # RECURRING-ERROR GUARDS (advisory; the user decides; each cites the rule).
    tc = trend_conflict(side, technicals)
    if tc:
        warnings.append(GateWarning("countertrend", "warn", tc))
    if _has_losing_same_dir(side, recent_closed_same_symbol):
        warnings.append(GateWarning("reentry_losing", "warn", RULE_REENTRY))
    if _has_losing_same_dir(side, open_same_symbol):
        warnings.append(GateWarning("adding_to_loser", "warn", RULE_ADDING))
    if require_thesis and not (thesis or "").strip():
        warnings.append(GateWarning("thesis_missing", "warn", RULE_THESIS))

    # BUDGET CAPS — committed risk per window (warn, or block if configured).
    budget_status = _budget_status(budget_caps, budget_used, risk_amount)
    for b in budget_status:
        if b["over"]:
            warnings.append(GateWarning(
                f"budget_{b['window']}", "block" if b["mode"] == "block" else "warn",
                f"Supereresti il budget di {b['label']}: {b['resulting']:.0f} impegnato / "
                f"{b['max']:.0f} max ({b['used']:.0f} già + {risk_amount:.0f} nuovo).",
            ))

    # KILL-SWITCH — soft blocks from the rules the user set when lucid. Blocking,
    # but the user can force it (recorded for the discipline scorecard).
    ks = dict(killswitch or {})
    if ks.get("enabled"):
        max_losses = int(ks.get("max_consecutive_losses", 0) or 0)
        if max_losses > 0 and consecutive_loss_count >= max_losses:
            until = f" fino a {ks['until']}" if ks.get("until") else ""
            warnings.append(GateWarning(
                "kill_switch_losses", "block",
                f"{consecutive_loss_count} perdite di fila: le tue regole dicono STOP{until}. "
                "Kill-switch che TU hai impostato quando eri lucido — forzalo solo consapevolmente.",
            ))
        cd = dict(cooldown or {})
        if cd.get("hours_ago") is not None:
            warnings.append(GateWarning(
                "cooldown", "block",
                f"Stop preso su {symbol} {side} {cd['hours_ago']:.0f}h fa: cooldown {cd.get('cooldown_hours')}h "
                "(anti-revenge). Aspetta prima di rientrare nello stesso verso.",
            ))

    has_blocking = any(w.severity == "block" for w in warnings)
    metrics = {
        "symbol": symbol, "side": side,
        "consecutive_losses": consecutive_loss_count, "cooldown": dict(cooldown or {}) or None,
        "risk_amount": risk_amount, "risk_pct": risk_pct, "stop_distance": stop_distance,
        "rr": rr, "resulting_heat_pct": resulting_heat_pct,
        "existing_heat_pct": existing_heat_pct, "n_concurrent": n_concurrent,
        "multiplier": multiplier, "lean_direction": lean_direction, "alignment": alignment,
        "atr": atr, "suggested_stop_distance": (stop_atr_min_multiple * atr) if atr else None,
        "budget": budget_status,
    }
    return {
        "metrics": metrics,
        "warnings": [asdict(w) for w in warnings],
        "has_blocking_warnings": has_blocking,
        "journal_draft": build_journal_draft(
            symbol=symbol, side=side, entry=entry, stop=stop, target=target,
            size=size, thesis=thesis, alignment=alignment, lean_direction=lean_direction,
            warnings=[asdict(w) for w in warnings],
        ),
        "caveat": GATE_CAVEAT,
    }


def _budget_status(caps: Mapping | None, used: Mapping | None,
                   risk_amount: float | None) -> list[dict]:
    """Per-window committed-risk status. Empty when no caps or no risk to add."""
    if not caps or risk_amount is None:
        return []
    used = used or {}
    out: list[dict] = []
    for win, label in (("day", "giornata"), ("week", "settimana"), ("month", "mese")):
        cap = caps.get(win)
        if not cap or cap.get("max") is None:
            continue
        mx = float(cap["max"])
        u = float(used.get(win) or 0.0)
        resulting = u + risk_amount
        out.append({
            "window": win, "label": label, "max": mx, "used": u,
            "resulting": resulting, "over": resulting > mx,
            "mode": cap.get("mode", "warn"),
        })
    return out


def build_journal_draft(
    *, symbol, side, entry, stop, target, size, thesis, alignment, lean_direction,
    warnings: Sequence[Mapping] = (),
) -> dict:
    """A journal entry pre-filled from the trade, to be linked to the position.

    Any breached guards are recorded in the note so the review can honestly count
    "how many times did I force a trade against my own rules"."""
    align_txt = {"aligned": "allineato alla marea macro",
                 "contrarian": "contrarian (contro la marea macro)"}.get(alignment, "n.d.")
    note = f"Allineamento macro: {align_txt}"
    if lean_direction:
        note += f" (lean: {lean_direction})"
    flagged = [w for w in (warnings or []) if w.get("severity") in ("warn", "block")]
    if flagged:
        note += " · Warning al momento dell'apertura: " + "; ".join(w["code"] for w in flagged)
    return {
        "symbol": symbol,
        "thesis": thesis or "",
        "entry_price": entry,
        "stop": stop,
        "size": size,
        "notes": note,
        "reviewed": False,
    }

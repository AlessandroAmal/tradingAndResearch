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

Honest by construction: the gate validates DISCIPLINE and RISK, not direction.

Tested in `worker/tests/test_gate.py`.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from . import risk as risk_math

GATE_CAVEAT = "Il gate valida disciplina e rischio, NON la direzione."


@dataclass(frozen=True)
class GateWarning:
    code: str
    severity: str        # 'warn' (a rule is breached) | 'info' (a note)
    message: str


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
) -> dict:
    """Validate a prospective trade. Returns metrics + warnings + a journal draft.
    Non-blocking: warnings inform; the user decides."""
    risk_amount = risk_math.open_risk(entry, stop, size, multiplier)
    risk_pct = risk_math.pct_of_account(risk_amount, account_size)
    rr = risk_math.r_multiple_potential(entry, stop, target)
    resulting_heat_pct = (existing_heat_pct or 0.0) + (risk_pct or 0.0)
    n_concurrent = open_count + 1

    warnings: list[GateWarning] = []
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

    metrics = {
        "symbol": symbol, "side": side,
        "risk_amount": risk_amount, "risk_pct": risk_pct,
        "rr": rr, "resulting_heat_pct": resulting_heat_pct,
        "existing_heat_pct": existing_heat_pct, "n_concurrent": n_concurrent,
        "multiplier": multiplier, "lean_direction": lean_direction, "alignment": alignment,
    }
    return {
        "metrics": metrics,
        "warnings": [asdict(w) for w in warnings],
        "has_blocking_warnings": False,   # never blocks — read-only
        "journal_draft": build_journal_draft(
            symbol=symbol, side=side, entry=entry, stop=stop, target=target,
            size=size, thesis=thesis, alignment=alignment, lean_direction=lean_direction,
        ),
        "caveat": GATE_CAVEAT,
    }


def build_journal_draft(
    *, symbol, side, entry, stop, target, size, thesis, alignment, lean_direction,
) -> dict:
    """A journal entry pre-filled from the trade, to be linked to the position."""
    align_txt = {"aligned": "allineato alla marea macro",
                 "contrarian": "contrarian (contro la marea macro)"}.get(alignment, "n.d.")
    note = f"Allineamento macro: {align_txt}"
    if lean_direction:
        note += f" (lean: {lean_direction})"
    return {
        "symbol": symbol,
        "thesis": thesis or "",
        "entry_price": entry,
        "stop": stop,
        "size": size,
        "notes": note,
        "reviewed": False,
    }

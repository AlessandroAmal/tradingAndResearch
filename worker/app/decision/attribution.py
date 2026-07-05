"""Event-driven context for the decision board — HONEST, never a forecast.

Four read-only helpers that put EVENTS where they are real, without ever fusing a
direction into the confluence lean (CLAUDE.md §1, §5):

  * macro_freshness  — flag FRED drivers whose last observation is stale (the feed
    lags; a recent event may not be reflected yet). Never estimates a value.
  * attribute_movement — "cosa ha mosso questo": the news/just-passed events/macro
    moves that explain the RECENT move (explicitly NOT the next one). Says so when
    nothing clearly explains it ("movimento non attribuito").
  * event_risk_banner — a structural flag when a HIGH-impact event is imminent;
    reuses the option-implied expected move for the ±% (calibrated, not invented).
  * dollar_note — for dollar-sensitive instruments, a co-movement context note.

Pure (no I/O); tested in `worker/tests/test_attribution.py` with mocked inputs.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta, timezone

# Keywords that make a just-passed calendar event a plausible macro catalyst.
_MACRO_EVENT_KW = ("payroll", "jobs", "lavoro", "nonfarm", "cpi", "pce", "inflation",
                   "inflazione", "fomc", "fed", "ecb", "bce", "unemployment", "gdp", "pil")


# --- A) macro freshness ----------------------------------------------
def business_days_between(start: date, end: date) -> int:
    """Weekdays strictly after `start` up to and including `end` (0 if start>=end)."""
    if start >= end:
        return 0
    days, d = 0, start
    while d < end:
        d += timedelta(days=1)
        if d.weekday() < 5:
            days += 1
    return days


def _as_date(v) -> date | None:
    if v is None:
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def macro_freshness(drivers: Sequence[Mapping], today: date,
                    stale_after_business_days: int = 2) -> dict:
    """Annotate each driver with staleness (does NOT mutate). Returns
    {drivers, any_stale, stale_labels, oldest_as_of}."""
    out = []
    any_stale = False
    stale_labels: list[str] = []
    oldest: date | None = None
    for d in drivers or ():
        dd = dict(d)
        as_of = _as_date(d.get("as_of"))
        age = business_days_between(as_of, today) if as_of else None
        stale = age is not None and age > stale_after_business_days
        dd["as_of_date"] = as_of.isoformat() if as_of else None
        dd["age_business_days"] = age
        dd["stale"] = stale
        if stale:
            any_stale = True
            stale_labels.append(d.get("label", d.get("id", "?")))
        if as_of and (oldest is None or as_of < oldest):
            oldest = as_of
        out.append(dd)
    return {
        "drivers": out,
        "any_stale": any_stale,
        "stale_labels": stale_labels,
        "oldest_as_of": oldest.isoformat() if oldest else None,
        "note": ("Alcuni driver macro sono ritardati: un evento recente potrebbe non "
                 "essere ancora riflesso. Non stimiamo valori mancanti." if any_stale else None),
    }


# --- B) movement attribution -----------------------------------------
def _dir_word(direction: str | None) -> str:
    return {"up": "su", "down": "giù"}.get(direction or "", "stabile")


def attribute_movement(
    *,
    instrument_name: str,
    recent_return_pct: float | None,
    news: Sequence[Mapping] = (),
    past_events: Sequence[Mapping] = (),
    drivers: Sequence[Mapping] = (),
    dollar_sensitivity: str | None = None,
    max_items: int = 5,
) -> dict:
    """Assemble the catalysts that explain the RECENT move. Honest: if nothing
    plausibly explains it, `attributed` is False and we say so."""
    items: list[dict] = []

    # Just-passed calendar events (the strongest, dated catalysts).
    macro_event = None
    for e in past_events or ():
        title = e.get("title") or ""
        imp = (e.get("importance") or "").lower()
        items.append({"kind": "event", "text": title,
                      "when": str(e.get("event_time"))[:16], "importance": imp})
        if macro_event is None and any(k in title.lower() for k in _MACRO_EVENT_KW):
            macro_event = title

    # Notable macro-driver moves (direction + the configured interpretation).
    dollar_dir = None
    for d in drivers or ():
        if d.get("direction") in ("up", "down") and d.get("interpretation"):
            items.append({"kind": "macro", "text": f"{d.get('label')} {_dir_word(d.get('direction'))}",
                          "detail": d.get("interpretation")})
        if d.get("id") == "DTWEXBGS":
            dollar_dir = d.get("direction")

    # Fresh per-instrument news.
    for n in news or ():
        if n.get("title"):
            items.append({"kind": "news", "text": n["title"],
                          "url": n.get("url"), "source": n.get("source"),
                          "when": n.get("published_at")})

    items = items[:max_items]

    # Explanatory CHAIN — only when the data supports it (dollar-sensitive
    # instrument + a macro event just passed + the dollar actually moved).
    chain: list[str] | None = None
    if dollar_sensitivity in ("inverse", "direct") and macro_event and dollar_dir in ("up", "down"):
        inverse = dollar_sensitivity == "inverse"
        ctx = ("rialzista" if (dollar_dir == "down") == inverse else "ribassista")
        chain = [macro_event, "attese Fed/tassi riviste",
                 f"dollaro {_dir_word(dollar_dir)}",
                 f"contesto {ctx} per {instrument_name}"]

    attributed = bool(items)
    return {
        "move_pct": recent_return_pct,
        "items": items,
        "chain": chain,
        "attributed": attributed,
        "label": "Spiega il movimento GIÀ avvenuto — non prevede il prossimo.",
        "note": (None if attributed else
                 "Nessun catalizzatore chiaro ingerito — movimento non attribuito."),
    }


# --- C) event-risk banner --------------------------------------------
def _parse_dt(s) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def event_risk_banner(events: Sequence[Mapping], implied: Mapping | None, *,
                      symbol: str, now: datetime, within_hours: float = 72.0,
                      importances: tuple[str, ...] = ("high",)) -> dict | None:
    """Nearest HIGH-impact event for `symbol` within the window + the option-implied
    expected move (±%) for the horizon closest to the event. None if none."""
    horizon = now + timedelta(hours=within_hours)
    best: tuple[datetime, Mapping] | None = None
    for e in events or ():
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
    if best is None:
        return None
    when, ev = best
    hours_to = (when - now).total_seconds() / 3600.0
    days_to = hours_to / 24.0
    # Expected move: the available implied horizon whose tenor is closest to the event.
    em = None
    horizons = [h for h in (implied or {}).get("horizons", [])
                if h.get("available") and h.get("expected_move_pct") is not None]
    if horizons:
        pick = min(horizons, key=lambda h: abs((h.get("days_to_expiry") or 0) - days_to))
        em = pick.get("expected_move_pct")
    return {
        "title": ev.get("title"),
        "event_time": str(ev.get("event_time")),
        "hours_to": hours_to,
        "expected_move_pct": em,
        "note": ("Dato/evento importante imminente — questa lettura di condizioni può "
                 "ribaltarsi dopo l'evento."),
    }


# --- D) dollar co-movement note --------------------------------------
def dollar_note(drivers: Sequence[Mapping], sensitivity: str | None) -> dict | None:
    """Context note for dollar-sensitive instruments (inverse/direct). None if the
    dollar driver (DTWEXBGS) is absent or flat."""
    if sensitivity not in ("inverse", "direct"):
        return None
    dv = next((d for d in drivers or () if d.get("id") == "DTWEXBGS"), None)
    if not dv or dv.get("value") is None:
        return None
    direction = dv.get("direction")
    if direction not in ("up", "down"):
        return None
    inverse = sensitivity == "inverse"
    favorable = (direction == "down") == inverse
    return {
        "sensitivity": sensitivity,
        "dollar_direction": direction,
        "context": "favorevole" if favorable else "contrario",
        "text": (
            "Inverso al dollaro: una notizia che muove il dollaro tende a muovere "
            "oro ed EUR/USD INSIEME. " if inverse else
            "Legato al dollaro: co-muove col dollaro. "
        ) + f"Il dollaro (DTWEXBGS) di recente: {_dir_word(direction)} → contesto "
            f"{'favorevole' if favorable else 'contrario'} (solo contesto, non una direzione da seguire).",
    }

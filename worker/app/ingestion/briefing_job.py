"""Briefing job: synthesise recent news + upcoming events + notable price
moves into a morning or intraday briefing, written to `briefings`.

Inputs are gathered defensively (a missing feed just yields fewer inputs).
The AI layer enforces brevity and the uncertainty caveat; this job only
assembles inputs and persists the result.
"""
from __future__ import annotations

from ..ai import AIClient
from ..ai.briefing import generate_briefing
from ..config import AppConfig
from ..indicators import daily_change
from ..logging_setup import get_logger
from ..storage import Storage

log = get_logger("ingestion.briefing")


def _notable_moves(cfg: AppConfig, storage: Storage) -> list[dict]:
    """Compute |daily %| moves above the configured threshold."""
    threshold = float(cfg.ai.get("notable_move_pct", 1.5))
    moves: list[dict] = []
    for inst in storage.list_instruments():
        iid = inst.get("id")
        if not iid:
            continue
        try:
            rows = storage.get_recent_prices(iid, 2)  # newest-first
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not read prices for %s: %s", inst.get("symbol"), exc)
            continue
        closes = [r["close"] for r in reversed(rows) if r.get("close") is not None]
        _, pct = daily_change(closes)
        if pct is not None and abs(pct) >= threshold:
            moves.append({"symbol": inst.get("symbol"), "change_pct": pct})
    moves.sort(key=lambda m: abs(m["change_pct"]), reverse=True)
    return moves


def run_briefing(
    cfg: AppConfig, storage: Storage, ai: AIClient, kind: str
) -> dict[str, int]:
    if not cfg.ai_enabled:
        log.info("AI disabled in config — skipping %s briefing", kind)
        return {"ok": 0, "failed": 0}
    if kind not in ("morning", "intraday"):
        raise ValueError(f"Unknown briefing kind: {kind!r}")

    lookback = int(cfg.ai.get("briefing_lookback_hours", 24))
    max_tokens = int(cfg.ai.get("briefing_max_tokens", 1200))

    try:
        news = storage.list_recent_news(lookback, 40)
        events = storage.list_upcoming_events(15)
        moves = _notable_moves(cfg, storage)
    except Exception as exc:  # noqa: BLE001
        log.error("Gathering briefing inputs failed: %s", exc)
        return {"ok": 0, "failed": 1}

    result = generate_briefing(
        ai,
        model=cfg.briefing_model,
        kind=kind,
        news=news,
        events=events,
        moves=moves,
        max_tokens=max_tokens,
    )
    if not result:
        log.error("Briefing generation returned nothing (kind=%s)", kind)
        return {"ok": 0, "failed": 1}

    try:
        storage.insert_briefing(
            {
                "kind": kind,
                "title": f"{kind.capitalize()} briefing",
                "body": result["content"],
                "model": cfg.briefing_model,
                "themes_covered": result.get("themes_covered", []),
                "uncertainty_note": result.get("uncertainty_note"),
            }
        )
    except Exception as exc:  # noqa: BLE001
        log.error("Storing briefing failed: %s", exc)
        return {"ok": 0, "failed": 1}

    log.info(
        "Briefing done (%s): %d news, %d events, %d moves",
        kind, len(news), len(events), len(moves),
    )
    return {"ok": 1, "failed": 0}

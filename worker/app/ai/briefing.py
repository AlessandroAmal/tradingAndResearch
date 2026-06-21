"""Briefing generation with Claude.

Two kinds:
  - "morning": a start-of-day synthesis of overnight news + the day's
    upcoming catalysts + notable moves.
  - "intraday": a tight "what matters now" update (~10 lines).

The system prompt enforces brevity, a scannable theme-tagged format, and
the honesty rule (CLAUDE.md §5): organise/synthesise only, flag
uncertainty, and never present any prediction or outcome as guaranteed.

Output is JSON: content (markdown), themes_covered, uncertainty_note.
"""
from __future__ import annotations

from typing import Any

from .client import AIClient

BRIEFING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "content": {"type": "string"},
        "themes_covered": {"type": "array", "items": {"type": "string"}},
        "uncertainty_note": {"type": "string"},
    },
    "required": ["content", "themes_covered", "uncertainty_note"],
    "additionalProperties": False,
}

_SHARED_RULES = (
    "You are a synthesis engine for a personal, READ-ONLY trading & research "
    "cockpit. You ORGANISE and SUMMARISE information; you are NOT a predictor "
    "and NOT giving financial advice. Hard rules: be tight and scannable; tag "
    "points by theme; never state any outcome as certain or guaranteed; flag "
    "uncertainty explicitly and note what is unknown or unconfirmed; do not "
    "fabricate facts, numbers, or events not present in the input. Put the "
    "uncertainty caveats in the 'uncertainty_note' field, not buried in prose. "
    "Use short markdown bullets."
)

_MORNING = (
    _SHARED_RULES
    + " Produce a MORNING briefing: a brief orientation for the day. Group by "
    "theme; for each, 1–2 bullets on what happened overnight and what to watch "
    "today. End 'content' with a one-line 'Today's catalysts' list. Keep it "
    "under ~16 lines."
)

_INTRADAY = (
    _SHARED_RULES
    + " Produce an INTRADAY 'what matters now' update: ~10 lines max, only the "
    "points that changed or matter right now. No preamble."
)


def _format_inputs(news, events, moves) -> str:
    lines: list[str] = []
    lines.append("RECENT NEWS (title — themes — instruments — source):")
    if news:
        for n in news:
            themes = ",".join(n.get("themes") or []) or "-"
            instr = ",".join(n.get("instruments") or []) or "-"
            lines.append(f"- {n.get('title')} — {themes} — {instr} — {n.get('source')}")
    else:
        lines.append("- (no recent news ingested)")

    lines.append("\nUPCOMING EVENTS (time — title — importance):")
    if events:
        for e in events:
            lines.append(
                f"- {e.get('event_time')} — {e.get('title')} — {e.get('importance') or '-'}"
            )
    else:
        lines.append("- (no upcoming events)")

    lines.append("\nNOTABLE PRICE MOVES (symbol — daily %):")
    if moves:
        for m in moves:
            lines.append(f"- {m.get('symbol')} — {m.get('change_pct'):+.2f}%")
    else:
        lines.append("- (no notable moves)")
    return "\n".join(lines)


def generate_briefing(
    ai: AIClient,
    *,
    model: str,
    kind: str,                       # "morning" | "intraday"
    news: list[dict[str, Any]],
    events: list[dict[str, Any]],
    moves: list[dict[str, Any]],
    max_tokens: int = 1200,
) -> dict[str, Any] | None:
    """Return {content, themes_covered, uncertainty_note} or None on failure."""
    system = _MORNING if kind == "morning" else _INTRADAY
    user = _format_inputs(news, events, moves)
    data = ai.json_call(
        model=model, system=system, user=user, schema=BRIEFING_SCHEMA, max_tokens=max_tokens
    )
    if not data or not data.get("content"):
        return None
    # Ensure the honesty caveat is never empty.
    if not data.get("uncertainty_note"):
        data["uncertainty_note"] = (
            "Synthesis only — not advice. Outcomes are uncertain; verify before acting."
        )
    data.setdefault("themes_covered", [])
    return data

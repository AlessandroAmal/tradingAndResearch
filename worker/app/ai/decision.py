"""Decision-board AI synthesis (M9) — describes, never predicts.

Takes the ASSEMBLED board (macro drivers, technicals, base rate, implied
probabilities, events, key-figure statements) and puts the setup into words:
which conditions point the same way, where the tensions are, what to watch.

Hard constraint (CLAUDE.md §5), enforced in the system prompt: it must NEVER
make a directional call (will rise / will fall / buy / sell), never present a
probability as a forecast, and always flag uncertainty. If the AI layer is off
or the call fails, the board simply saves without a summary.

Output JSON: summary (markdown), tensions[], uncertainty_note.
"""
from __future__ import annotations

import json
from typing import Any

from .client import AIClient

DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "tensions": {"type": "array", "items": {"type": "string"}},
        "uncertainty_note": {"type": "string"},
    },
    "required": ["summary", "tensions", "uncertainty_note"],
    "additionalProperties": False,
}

_SYSTEM = (
    "You are a synthesis engine for a personal, READ-ONLY trading cockpit. Given a "
    "structured 'decision board' for ONE instrument, DESCRIBE the current setup in "
    "tight, scannable Italian. ABSOLUTE rules: do NOT make a directional call "
    "(never say it will rise/fall, never buy/sell/hold); do NOT present any "
    "probability as a forecast — the implied probabilities are the market's odds, "
    "and the base rate is a historical frequency with a sample size, not a "
    "prediction; if a base rate's sample is insufficient or zero, say so and draw "
    "NO conclusion from it; explicitly flag uncertainty. Describe which conditions "
    "align and which conflict (the 'tensions'), and what upcoming events could "
    "change the picture. The 'synthesis' field is the alignment of CURRENT "
    "conditions (a lean), NOT a probability — describe the tension between that "
    "lean and the market's implied odds (e.g. 'conditions lean bearish but the "
    "market is ~neutral, so the move may already be priced in'), WITHOUT turning "
    "the lean into a probability. Put caveats in 'uncertainty_note'. Be concise (≤12 lines)."
)


def summarize_decision_board(
    ai: AIClient, *, model: str, board: dict[str, Any], max_tokens: int = 600
) -> dict[str, Any] | None:
    """Return {summary, tensions, uncertainty_note} or None on failure."""
    # Feed a compact JSON view; the model reads facts, not prose.
    compact = {
        "instrument": board.get("name") or board.get("symbol"),
        "last": board.get("last"),
        "macro_drivers": board.get("macro_drivers"),
        "technicals": board.get("technicals"),
        "base_rate": board.get("base_rate"),
        "implied": board.get("implied"),
        "synthesis": board.get("synthesis"),
        "upcoming_events": board.get("events"),
        "figure_statements": board.get("figures"),
    }
    user = "DECISION BOARD (facts only):\n" + json.dumps(compact, default=str, ensure_ascii=False)
    data = ai.json_call(
        model=model, system=_SYSTEM, user=user, schema=DECISION_SCHEMA, max_tokens=max_tokens
    )
    if not data or not data.get("summary"):
        return None
    if not data.get("uncertainty_note"):
        data["uncertainty_note"] = (
            "Sintesi descrittiva, non una previsione. Le probabilità sono implicite "
            "nei prezzi; le decisioni restano tue."
        )
    data.setdefault("tensions", [])
    return data

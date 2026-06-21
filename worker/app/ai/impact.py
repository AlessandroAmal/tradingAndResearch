"""Key-figure impact mapping with Claude (M4 / brief §8).

For a new figure statement, map which universe instruments it could move
and a one-line rationale. Affected instruments are schema-constrained to
the configured universe (the model cannot invent a ticker), and the model
is instructed to return an EMPTY list when there is no clear impact rather
than guessing. Honesty rule (CLAUDE.md §5): the rationale must not state
outcomes as certain.
"""
from __future__ import annotations

from typing import Any

from .client import AIClient

IMPACT_SYSTEM = (
    "You map financial impact for a personal, read-only trading cockpit. "
    "Given a statement by a tracked public figure, decide which of the "
    "provided INSTRUMENTS (by ticker) it could plausibly move, and write a "
    "single-line rationale. Rules: choose ONLY from the instruments given; "
    "never invent a ticker; if there is no clear, well-supported market "
    "impact, return an EMPTY list and say so. Do NOT state outcomes as "
    "certain — phrase the rationale as a possible influence, not a "
    "prediction. Keep 'why_it_matters' to one sentence. Return JSON only."
)


def build_impact_schema(symbols: list[str]) -> dict[str, Any]:
    instr_items: dict[str, Any] = {"type": "string"}
    if symbols:
        instr_items["enum"] = symbols
    return {
        "type": "object",
        "properties": {
            "affected_instruments": {"type": "array", "items": instr_items},
            "why_it_matters": {"type": "string"},
        },
        "required": ["affected_instruments", "why_it_matters"],
        "additionalProperties": False,
    }


def map_statement_impact(
    ai: AIClient,
    *,
    model: str,
    figure: str,
    role: str | None,
    text: str,
    symbols: list[str],
    max_tokens: int = 400,
) -> dict[str, Any]:
    """Return {'affected_instruments': [...], 'why_it_matters': str}.

    Defaults to empty/honest output on any failure or uncertainty.
    """
    schema = build_impact_schema(symbols)
    user = (
        f"INSTRUMENTS: {', '.join(symbols) or '(none)'}\n\n"
        f"Figure: {figure}" + (f" ({role})" if role else "") + "\n"
        f"Statement: {text}\n\n"
        "Return the affected instruments (empty if none clearly apply) and a "
        "one-line why_it_matters."
    )
    data = ai.json_call(
        model=model, system=IMPACT_SYSTEM, user=user, schema=schema, max_tokens=max_tokens
    )
    if not data:
        return {"affected_instruments": [], "why_it_matters": ""}

    instr = [s for s in data.get("affected_instruments", []) if s in symbols]
    why = data.get("why_it_matters") or ""
    if not isinstance(why, str):
        why = ""
    return {"affected_instruments": instr, "why_it_matters": why.strip()}

"""Per-item news tagging with Claude.

Given a news item, classify it by THEME and by AFFECTED INSTRUMENTS,
choosing ONLY from the configured theme/universe lists. The model is
instructed (and schema-constrained) to return empty lists when unsure
rather than inventing tags — this keeps the data honest and cheap.

Output is constrained to a JSON schema whose arrays are `enum`-limited to
the known themes/symbols, so the model literally cannot return a value
outside the universe.
"""
from __future__ import annotations

from typing import Any

from .client import AIClient

TAGGING_SYSTEM = (
    "You tag financial news items for a personal, read-only trading cockpit. "
    "For each item, decide which of the provided THEMES it concerns and which "
    "of the provided INSTRUMENTS (by ticker) it could plausibly affect. "
    "Rules: choose ONLY from the lists given; never invent a theme or ticker; "
    "if you are unsure or the item is irrelevant, return empty lists. Do not "
    "guess relationships that aren't clearly supported by the title. "
    "Return JSON only."
)


def build_tagging_schema(themes: list[str], symbols: list[str]) -> dict[str, Any]:
    """JSON schema constraining tags to known themes/symbols (or empty)."""
    theme_items: dict[str, Any] = {"type": "string"}
    if themes:
        theme_items["enum"] = themes
    symbol_items: dict[str, Any] = {"type": "string"}
    if symbols:
        symbol_items["enum"] = symbols
    return {
        "type": "object",
        "properties": {
            "themes": {"type": "array", "items": theme_items},
            "instruments": {"type": "array", "items": symbol_items},
        },
        "required": ["themes", "instruments"],
        "additionalProperties": False,
    }


def tag_news_item(
    ai: AIClient,
    *,
    model: str,
    title: str,
    source: str,
    summary: str | None,
    themes: list[str],
    symbols: list[str],
    max_tokens: int = 400,
) -> dict[str, list[str]]:
    """Return {'themes': [...], 'instruments': [...]} — empty on uncertainty."""
    schema = build_tagging_schema(themes, symbols)
    user = (
        f"THEMES: {', '.join(themes) or '(none)'}\n"
        f"INSTRUMENTS: {', '.join(symbols) or '(none)'}\n\n"
        f"News item:\n"
        f"- source: {source}\n"
        f"- title: {title}\n"
        + (f"- summary: {summary}\n" if summary else "")
        + "\nReturn the relevant themes and instruments (empty lists if unsure)."
    )
    data = ai.json_call(
        model=model, system=TAGGING_SYSTEM, user=user, schema=schema, max_tokens=max_tokens
    )
    if not data:
        return {"themes": [], "instruments": []}

    # Defensive: keep only known values even though the schema enforces it.
    out_themes = [t for t in data.get("themes", []) if t in themes]
    out_instr = [s for s in data.get("instruments", []) if s in symbols]
    return {"themes": out_themes, "instruments": out_instr}

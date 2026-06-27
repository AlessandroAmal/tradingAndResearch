"""Decision-board AI synthesis (M9) — interprets, never predicts.

The PAID action (Anthropic API). It reads the assembled board — the REAL
probabilities already computed (option-IMPLIED, including P(above/below) a
user level) and the historical base rates — and the current conditions, then
writes an HONEST, conditional reading:
  - a short narrative of the setup and the conditions↔market tension,
  - explicit upside / downside scenarios (what would drive each),
  - what to watch at the next event,
  - a QUALITATIVE conviction (alta/media/bassa).

HARD rules (CLAUDE.md §1, §5), enforced in the system prompt:
  * NO single "directional probability" number (never "X% it rises"). The ONLY
    probabilities it may cite are the REAL ones it is given (option-implied /
    base rates), labelled as market odds / historical frequency.
  * Never a directional call presented as certainty, never an operational
    recommendation (no buy/sell/hold/size).
  * Always flag uncertainty. If a base rate's sample is insufficient/zero, say so
    and draw no conclusion.

Output JSON: read, upside_drivers[], downside_drivers[], watch_next_event[],
conviction, uncertainty_note.
"""
from __future__ import annotations

import json
from typing import Any

from .client import AIClient

DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "read": {"type": "string"},
        "upside_drivers": {"type": "array", "items": {"type": "string"}},
        "downside_drivers": {"type": "array", "items": {"type": "string"}},
        "watch_next_event": {"type": "array", "items": {"type": "string"}},
        "conviction": {"type": "string", "enum": ["alta", "media", "bassa"]},
        "uncertainty_note": {"type": "string"},
    },
    "required": ["read", "upside_drivers", "downside_drivers",
                 "watch_next_event", "conviction", "uncertainty_note"],
    "additionalProperties": False,
}

_SYSTEM = (
    "Sei un motore di sintesi per un cockpit di trading READ-ONLY. Dato un "
    "'decision board' strutturato per UNO strumento, interpreta il setup in "
    "italiano, conciso e scannabile. REGOLE ASSOLUTE: (1) NON produrre alcun "
    "numero di 'probabilità direzionale' tuo (mai 'X% sale/scende'); le UNICHE "
    "probabilità che puoi citare sono quelle REALI fornite — implicite nelle "
    "opzioni (inclusa P(sopra/sotto) il livello dell'utente) e i base rate "
    "storici — etichettandole come odds del mercato o frequenza storica. (2) Se "
    "un base rate ha campione insufficiente o nullo, dillo e non trarne "
    "conclusioni. (3) La 'lettura di confluenza' è l'allineamento delle "
    "condizioni ATTUALI, NON una previsione: descrivi la tensione tra questa e "
    "gli odds del mercato senza trasformarla in probabilità. (4) Niente "
    "raccomandazioni operative (mai comprare/vendere/tenere o dimensionare). "
    "(5) Segnala sempre l'incertezza. Fornisci scenari condizionali: cosa "
    "spingerebbe al rialzo (upside_drivers) e al ribasso (downside_drivers), "
    "cosa monitorare al prossimo evento (watch_next_event), e una convinzione "
    "QUALITATIVA (alta/media/bassa) sul grado di allineamento — non sull'esito. "
    "Metti i caveat in 'uncertainty_note'. Sii breve."
)


def summarize_decision_board(
    ai: AIClient,
    *,
    model: str,
    board: dict[str, Any],
    level_probs: dict[str, Any] | None = None,
    max_tokens: int = 1500,
) -> dict[str, Any] | None:
    """Return the honest AI reading dict, or None on failure.

    `level_probs` (optional) are the REAL option-implied P(above/below) at a
    user-chosen level, computed server-side — passed through for the model to
    interpret (never invented)."""
    compact = {
        "instrument": board.get("name") or board.get("symbol"),
        "last": board.get("last"),
        "macro_drivers": board.get("macro_drivers"),
        "technicals": board.get("technicals"),
        "base_rate": board.get("base_rate"),
        "implied_probabilities": board.get("implied"),
        "implied_at_user_level": level_probs,
        "synthesis_confluence_read": board.get("synthesis"),
        "upcoming_events": board.get("events"),
        "figure_statements": board.get("figures"),
    }
    user = ("DECISION BOARD (solo fatti; le probabilità qui sono REALI — "
            "implicite nelle opzioni o frequenze storiche):\n"
            + json.dumps(compact, default=str, ensure_ascii=False))
    data = ai.json_call(
        model=model, system=_SYSTEM, user=user, schema=DECISION_SCHEMA, max_tokens=max_tokens
    )
    if not data or not data.get("read"):
        return None
    if not data.get("uncertainty_note"):
        data["uncertainty_note"] = (
            "Sintesi descrittiva, non una previsione. Le uniche probabilità sono "
            "implicite nei prezzi / storiche; le decisioni restano tue."
        )
    for k in ("upside_drivers", "downside_drivers", "watch_next_event"):
        data.setdefault(k, [])
    data.setdefault("conviction", "bassa")
    return data

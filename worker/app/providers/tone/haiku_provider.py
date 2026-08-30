"""Haiku-based ToneProvider — cheap qualitative language read of a quarter's comms.

Uses the AIClient (server-side) with a schema that has NO numeric/directional
field. Gates on text sufficiency BEFORE calling the model: too little accessible
text -> evaluable=False (never invented).
"""
from __future__ import annotations

import json
from typing import Any

from ...logging_setup import get_logger
from .base import TONE_LABEL, ToneProvider

log = get_logger("provider.tone.haiku")

MIN_CHARS = 400          # below this, there isn't enough text to read honestly

# No numeric score anywhere — only categorical language descriptors + prose.
TONE_SCHEMA = {
    "type": "object",
    "properties": {
        "guidance": {"type": "string", "enum": ["alzata", "abbassata", "confermata", "non menzionata"]},
        "caution_confidence": {"type": "string", "enum": ["più cauto", "più fiducioso", "misto", "neutro"]},
        "summary": {"type": "string"},
        "changes_vs_prior": {"type": "string"},
        "themes_new": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
        "themes_gone": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
    },
    "required": ["guidance", "caution_confidence", "summary", "themes_new", "themes_gone"],
    "additionalProperties": False,
}

_SYSTEM = (
    "Sei un lettore QUALITATIVO del LINGUAGGIO delle comunicazioni aziendali di UN "
    "trimestre (comunicati utili + news collegate). Descrivi COME parla il "
    "management: guidance alzata/abbassata/confermata, parole di cautela vs "
    "fiducia, temi nuovi o spariti. Se ricevi il trimestre precedente, di' COSA È "
    "CAMBIATO nel modo di parlare. REGOLE ASSOLUTE: (1) MAI un numero o una "
    "probabilità direzionale, MAI 'salirà/scenderà'; NON assumere l'impatto sul "
    "titolo. (2) Attieniti al testo fornito: se un aspetto non c'è, usa 'non "
    "menzionata'/'neutro', non inventare. (3) Italiano, conciso: summary ~80 "
    "parole. È contesto qualitativo, non una previsione."
)


class HaikuToneProvider(ToneProvider):
    name = "haiku"

    def __init__(self, ai, model: str) -> None:
        self._ai = ai
        self._model = model

    def read_quarter(self, symbol: str, period_label: str, texts: list[dict],
                     prior: dict | None = None) -> dict[str, Any]:
        joined = "\n\n".join(
            f"[{t.get('source', '?')} · {t.get('date', '')}] {t.get('title', '')}\n{t.get('body', '')}"
            for t in (texts or [])
        ).strip()
        if len(joined) < MIN_CHARS:
            return {"evaluable": False, "summary": None,
                    "note": "tono: non valutabile (nessuna trascrizione accessibile)",
                    "sources": [t.get("title") for t in (texts or [])], "label": TONE_LABEL}
        prior_txt = ""
        if prior and prior.get("summary"):
            prior_txt = (f"\n\nTRIMESTRE PRECEDENTE ({prior.get('period_label', '')}) — "
                         f"come parlavano allora:\n{prior['summary']}")
        user = (f"AZIENDA: {symbol} — TRIMESTRE {period_label}\n"
                f"TESTI (comunicati + news collegate):\n{joined}{prior_txt}")
        data = self._ai.json_call(model=self._model, system=_SYSTEM, user=user,
                                  schema=TONE_SCHEMA, max_tokens=900)
        if not data or not data.get("summary"):
            return {"evaluable": False, "summary": None,
                    "note": "tono: non valutabile (lettura non riuscita)",
                    "sources": [t.get("title") for t in (texts or [])], "label": TONE_LABEL}
        data["evaluable"] = True
        data["sources"] = [{"title": t.get("title"), "source": t.get("source"),
                            "date": t.get("date")} for t in (texts or [])]
        data.setdefault("changes_vs_prior", "" if not prior else data.get("changes_vs_prior", ""))
        data["note"] = TONE_LABEL
        return data


def build_tone_provider(name: str, ai, model: str) -> ToneProvider:
    name = (name or "haiku").lower()
    if name == "haiku":
        return HaikuToneProvider(ai, model)
    raise ValueError(f"Unknown tone provider: {name!r}")

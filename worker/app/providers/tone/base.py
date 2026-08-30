"""ToneProvider interface — a QUALITATIVE read of the LANGUAGE in a quarter's
communications (earnings press releases + linked news; public transcripts only if
freely accessible — never scrape sources that forbid it).

Honesty (CLAUDE.md): if there isn't enough accessible text, the reading is
`evaluable=False` ("tono: non valutabile") — NEVER invented. There is NO numeric
or directional score: the impact on the stock is NOT assumed here; it will be
MEASURED as a candidate factor in the calibration once enough quarters accumulate.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

# Fixed honest label shown wherever a tone reading appears.
TONE_LABEL = ("lettura qualitativa del linguaggio; l'impatto sul titolo NON è "
              "assunto — verrà misurato come fattore candidato quando lo storico "
              "basterà")


@runtime_checkable
class ToneProvider(Protocol):
    name: str

    def read_quarter(self, symbol: str, period_label: str, texts: list[dict],
                     prior: dict | None = None) -> dict[str, Any]:
        """Read the tone for one quarter from `texts` (each {title, body, source,
        date}); `prior` is the previous quarter's reading for comparison. Returns
        {evaluable, guidance, caution_confidence, summary, changes_vs_prior,
        themes_new, themes_gone, sources, note}. Never a number; never invented."""
        ...

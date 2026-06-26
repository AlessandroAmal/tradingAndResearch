"""Decision board (M9) — per-instrument confluence cockpit, gold first.

Assembles, for one instrument, the context the user weighs BEFORE a trade:
macro drivers, technicals, an honest historical base rate, and the option-
implied (market-odds) probabilities. It is NOT a signal and NEVER a prediction
(CLAUDE.md §1, §5). Generalises to any instrument by changing the driver set in
config — only the gold board is enabled today.
"""
from .board import build_confluence, run_decision_board
from .implied import implied_probabilities
from .synthesis import confluence_read

__all__ = [
    "run_decision_board",
    "build_confluence",
    "implied_probabilities",
    "confluence_read",
]

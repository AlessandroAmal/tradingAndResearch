"""Research / backtesting bench (Phase 4).

READ-ONLY research tool to MEASURE whether a technical rule has edge — built to
make overfitting VISIBLE (out-of-sample + costs + multi-instrument + deflated
Sharpe + bootstrap), never a signal generator and never an order machine
(CLAUDE.md). See `engine.py` (no look-ahead, t+1 open, costs) and `safeguards.py`.
"""
from .runner import run_scan, run_single

__all__ = ["run_single", "run_scan"]

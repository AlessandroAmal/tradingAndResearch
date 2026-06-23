"""Alert engine (M8) — evaluates rules/flags and notifies. Read-only."""
from .engine import run_alert_evaluation

__all__ = ["run_alert_evaluation"]

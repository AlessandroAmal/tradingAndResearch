"""Pure alert-rule logic (M8) — no I/O, fully unit-tested.

Anti-spam is the point here: an alert fires when the condition BECOMES true
(edge), and only re-fires while it stays true after a configurable cooldown —
never every cycle. This module holds that decision logic in isolation.
"""
from __future__ import annotations

from datetime import datetime


def threshold_met(op: str, current: float | None, threshold: float) -> bool:
    """Price/IV condition. op = 'above' (>=) | 'below' (<=)."""
    if current is None:
        return False
    if op == "above":
        return current >= threshold
    if op == "below":
        return current <= threshold
    return False


def should_fire(
    condition_now: bool,
    last_state: bool,
    last_triggered: datetime | None,
    cooldown_seconds: int,
    now: datetime,
) -> bool:
    """Edge-triggered with cooldown re-fire.

    - condition false        -> never fire
    - became true (edge)     -> fire
    - still true, no record  -> fire
    - still true within cd   -> suppress
    - still true past cd     -> fire again
    """
    if not condition_now:
        return False
    if not last_state:
        return True
    if last_triggered is None:
        return True
    return (now - last_triggered).total_seconds() >= cooldown_seconds

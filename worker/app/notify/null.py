"""Null notifier — used when no channel is configured.

The alert job still evaluates rules and logs would-be alerts; dispatch is
skipped (CLAUDE.md graceful degradation). send() logs and returns False.
"""
from __future__ import annotations

from ..logging_setup import get_logger

log = get_logger("notify.null")


class NullNotifier:
    name = "none"

    def send(self, text: str) -> bool:
        log.info("Alert dispatch skipped (no channel configured): %s", text.split("\n", 1)[0])
        return False

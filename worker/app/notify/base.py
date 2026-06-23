"""Notifier interface (M8).

Alert channels sit behind this interface so Telegram (today) can be swapped
or joined by email later without touching the alert engine (CLAUDE.md §4).
Notifiers NOTIFY — they never execute anything. Tokens live server-side
(worker .env), never in the browser.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Notifier(Protocol):
    name: str

    def send(self, text: str) -> bool:
        """Deliver a message. Return True if delivered, False otherwise.

        Must NOT raise — a channel being down degrades gracefully (the alert
        is still logged with delivered=false).
        """
        ...

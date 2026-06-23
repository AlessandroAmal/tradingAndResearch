"""Alert channels, behind the Notifier interface (CLAUDE.md §4)."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from ..logging_setup import get_logger
from .base import Notifier
from .null import NullNotifier
from .telegram import TelegramNotifier

if TYPE_CHECKING:
    from ..config import AppConfig

log = get_logger("notify")

__all__ = ["Notifier", "NullNotifier", "TelegramNotifier", "build_notifier"]


def build_notifier(cfg: "AppConfig") -> Notifier:
    """Telegram if configured + enabled, else a NullNotifier (logs skip).

    Email is intentionally OFF (prepared interface only).
    """
    channels = (cfg.alerts or {}).get("channels", {})
    telegram_on = channels.get("telegram", True)
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if telegram_on and token and chat_id:
        log.info("Alert channel: Telegram")
        return TelegramNotifier(token, chat_id)
    log.warning("Alert channel not configured (set TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID) — dispatch will be skipped")
    return NullNotifier()

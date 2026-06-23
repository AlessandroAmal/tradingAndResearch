"""Telegram notifier (primary channel, M8).

Token + chat id come from the worker .env (TELEGRAM_BOT_TOKEN /
TELEGRAM_CHAT_ID) — never the browser. send() returns True/False and never
raises, so a network/API failure just logs and the alert is recorded as
not-delivered.
"""
from __future__ import annotations

import httpx

from ..logging_setup import get_logger

log = get_logger("notify.telegram")


class TelegramNotifier:
    name = "telegram"

    def __init__(self, token: str, chat_id: str, timeout: float = 15.0) -> None:
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"
        self._chat_id = chat_id
        self._timeout = timeout

    def send(self, text: str) -> bool:
        try:
            resp = httpx.post(
                self._url,
                json={"chat_id": self._chat_id, "text": text, "disable_web_page_preview": True},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            log.error("Telegram send failed: %s", exc)
            return False

"""Tiny retry/backoff helper for ingestion calls (no extra deps)."""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from ..logging_setup import get_logger

log = get_logger("ingestion.retry")
T = TypeVar("T")


def with_retry(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 1.0,
    label: str = "operation",
) -> T:
    """Call `fn`, retrying with exponential backoff on exception.

    Re-raises the last exception after exhausting attempts so the caller
    can log a clear failure.
    """
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — ingestion must catch broadly
            last = exc
            if attempt < attempts:
                delay = base_delay * (2 ** (attempt - 1))
                log.warning(
                    "%s failed (attempt %d/%d): %s — retrying in %.1fs",
                    label, attempt, attempts, exc, delay,
                )
                time.sleep(delay)
            else:
                log.error("%s failed after %d attempts: %s", label, attempts, exc)
    assert last is not None
    raise last

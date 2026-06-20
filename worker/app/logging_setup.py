"""Centralised logging configuration.

Ingestion failures must be obvious in the logs (CLAUDE.md engineering
standards), so we use a clear, timestamped format and let the level be
controlled by the LOG_LEVEL env var.
"""
from __future__ import annotations

import logging
import os


def setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

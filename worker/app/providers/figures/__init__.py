"""Figure sources, each behind the FigureSource interface (CLAUDE.md §4)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from .base import FigureSource, FigureStatement
from .news_source import NewsFigureSource

if TYPE_CHECKING:
    from ...config import AppConfig

__all__ = [
    "FigureSource",
    "FigureStatement",
    "NewsFigureSource",
    "build_figure_source",
]


def build_figure_source(cfg: "AppConfig") -> FigureSource:
    """Factory: select the FigureSource implementation.

    Default reuses the free news mechanics (Google News RSS + press feeds).
    Swap here to plug a different source without touching ingestion.
    """
    src = (cfg.news or {}).get("figures_source", "news")
    if src == "news":
        return NewsFigureSource(filter_cfg=(cfg.news or {}).get("figures_filter", {}))
    raise ValueError(f"Unknown figure source: {src!r}")

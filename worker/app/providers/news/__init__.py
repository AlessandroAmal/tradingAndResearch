"""News providers, each behind the NewsProvider interface (CLAUDE.md §4)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from .base import NewsItem, NewsProvider
from .gdelt_provider import GDELTNewsProvider
from .rss_provider import RSSNewsProvider

if TYPE_CHECKING:
    from ...config import AppConfig

__all__ = [
    "NewsItem",
    "NewsProvider",
    "GDELTNewsProvider",
    "RSSNewsProvider",
    "build_news_providers",
]


def build_news_providers(cfg: "AppConfig") -> list[NewsProvider]:
    """Factory: assemble the enabled NewsProviders from config.

    Returns a list so the ingestion job can fan out across sources and
    merge/dedupe the results. NewsAPI is optional and off by default.
    """
    news = cfg.news or {}
    providers: list[NewsProvider] = []

    gdelt = news.get("gdelt", {})
    if gdelt.get("enabled", True):
        providers.append(
            GDELTNewsProvider(
                timespan=gdelt.get("timespan", "1d"),
                max_records=int(gdelt.get("max_records", 60)),
            )
        )

    rss = news.get("rss", {})
    if rss.get("enabled", True):
        providers.append(RSSNewsProvider(feeds=rss.get("feeds", [])))

    # NewsAPI is intentionally optional/off by default (requires a key and
    # has restrictive free-tier terms). Wire it in here when enabled.
    return providers

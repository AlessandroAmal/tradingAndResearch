"""News ingestion job: fetch from all NewsProviders -> news_items.

Per-provider isolation (one source failing doesn't abort the others),
retry/backoff, dedup by url AND title before writing. Items are stored
UNtagged; the AI tagging job fills themes/instruments later.
"""
from __future__ import annotations

from ..config import AppConfig
from ..logging_setup import get_logger
from ..providers.news import NewsItem, NewsProvider
from ..storage import Storage
from .retry import with_retry

log = get_logger("ingestion.news")


def run_news_ingestion(
    cfg: AppConfig, storage: Storage, providers: list[NewsProvider]
) -> dict[str, int]:
    keywords = list((cfg.news or {}).get("keywords", []))
    collected: list[NewsItem] = []
    failed = 0

    for provider in providers:
        try:
            items = with_retry(
                lambda p=provider: p.fetch(keywords),
                label=f"news.fetch({provider.name})",
            )
            collected.extend(items)
        except Exception as exc:  # noqa: BLE001 — isolate per-provider
            failed += 1
            log.error("News provider %s failed: %s", provider.name, exc)

    rows = _dedupe_rows(collected)
    try:
        storage.upsert_news_items(rows)
    except Exception as exc:  # noqa: BLE001
        log.error("Storing news items failed: %s", exc)
        return {"ok": 0, "failed": failed + 1}

    log.info("News ingestion done: %d unique items, %d providers failed", len(rows), failed)
    return {"ok": len(rows), "failed": failed}


def _dedupe_rows(items: list[NewsItem]) -> list[dict]:
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    rows: list[dict] = []
    for it in items:
        title_key = it.title.strip().lower()
        if it.url in seen_urls or title_key in seen_titles:
            continue
        seen_urls.add(it.url)
        seen_titles.add(title_key)
        rows.append(
            {
                "title": it.title,
                "url": it.url,
                "source": it.source,
                "published_at": it.published_at.isoformat() if it.published_at else None,
                "summary": it.summary,
            }
        )
    return rows

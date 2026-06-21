"""AI tagging job: tag new, relevant news items with Claude.

Cost control (CLAUDE.md / brief): only untagged items are processed, and
at most `ai.tagging_max_items` per run. Each item is one cheap Claude call
returning ONLY {themes[], instruments[]} constrained to the universe; on
any failure the item is left for a later run rather than mis-tagged.
"""
from __future__ import annotations

from ..ai import AIClient
from ..ai.tagging import tag_news_item
from ..config import AppConfig
from ..logging_setup import get_logger
from ..storage import Storage

log = get_logger("ingestion.tagging")


def run_tagging(cfg: AppConfig, storage: Storage, ai: AIClient) -> dict[str, int]:
    if not cfg.ai_enabled:
        log.info("AI disabled in config — skipping tagging")
        return {"ok": 0, "failed": 0}

    max_items = int(cfg.ai.get("tagging_max_items", 40))
    max_tokens = int(cfg.ai.get("tagging_max_tokens", 400))
    themes = list(cfg.themes)
    symbols = cfg.symbols

    items = storage.list_untagged_news(max_items)
    if not items:
        log.info("No untagged news items")
        return {"ok": 0, "failed": 0}

    ok, failed = 0, 0
    for item in items:
        try:
            tags = tag_news_item(
                ai,
                model=cfg.tagging_model,
                title=item.get("title", ""),
                source=item.get("source", ""),
                summary=item.get("summary"),
                themes=themes,
                symbols=symbols,
                max_tokens=max_tokens,
            )
            storage.update_news_tags(item["id"], tags["themes"], tags["instruments"])
            ok += 1
        except Exception as exc:  # noqa: BLE001 — isolate per-item
            failed += 1
            log.error("Tagging failed for item %s: %s", item.get("id"), exc)

    log.info("Tagging done: %d tagged, %d failed (model=%s)", ok, failed, cfg.tagging_model)
    return {"ok": ok, "failed": failed}

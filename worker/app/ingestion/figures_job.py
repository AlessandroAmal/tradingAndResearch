"""Key-figure ingestion job (M4): fetch statements per figure -> figure_statements.

Per-figure isolation (one figure failing doesn't abort the rest),
retry/backoff, dedup by url AND text before writing. Statements are stored
UNmapped; the AI impact-mapping job fills affected_instruments /
why_it_matters later.

Writes the canonical columns (figure, role, statement, source, url,
stated_at) — `statement` is the existing NOT NULL text column (no
headline/title-style drift).
"""
from __future__ import annotations

from ..config import AppConfig
from ..logging_setup import get_logger
from ..providers.figures import FigureSource, FigureStatement
from ..storage import Storage
from .retry import with_retry

log = get_logger("ingestion.figures")


def run_figures_ingestion(
    cfg: AppConfig, storage: Storage, source: FigureSource
) -> dict[str, int]:
    figures = cfg.figures or []
    collected: list[FigureStatement] = []
    failed = 0

    for fig in figures:
        name = fig.get("name", "?")
        try:
            items = with_retry(
                lambda f=fig: source.fetch(f),
                label=f"figures.fetch({name})",
            )
            collected.extend(items)
        except Exception as exc:  # noqa: BLE001 — isolate per-figure
            failed += 1
            log.error("Figure source failed for %s: %s", name, exc)

    rows = _dedupe_rows(collected)
    try:
        storage.upsert_figure_statements(rows)
    except Exception as exc:  # noqa: BLE001
        log.error("Storing figure statements failed: %s", exc)
        return {"ok": 0, "failed": failed + 1}

    log.info(
        "Figures ingestion done: %d unique statements, %d figures failed",
        len(rows), failed,
    )
    return {"ok": len(rows), "failed": failed}


def _dedupe_rows(items: list[FigureStatement]) -> list[dict]:
    seen_urls: set[str] = set()
    seen_text: set[str] = set()
    rows: list[dict] = []
    for it in items:
        text_key = (it.figure + "|" + it.text).strip().lower()
        if (it.url and it.url in seen_urls) or text_key in seen_text:
            continue
        if it.url:
            seen_urls.add(it.url)
        seen_text.add(text_key)
        rows.append(
            {
                "figure": it.figure,
                "role": it.role,
                "statement": it.text,   # canonical text column (NOT NULL)
                "source": it.source,
                "url": it.url,
                "stated_at": it.stated_at.isoformat() if it.stated_at else None,
            }
        )
    return rows

"""AI impact-mapping job (M4): map new figure statements to instruments.

Cost control: only unprocessed statements (processed_at IS NULL), capped at
`ai.figures_max_items` per run. Each is one cheap Claude call returning ONLY
{affected_instruments[], why_it_matters}, constrained to the universe; on
failure the statement is left for a later run rather than mis-mapped.
"""
from __future__ import annotations

from ..ai import AIClient
from ..ai.impact import map_statement_impact
from ..config import AppConfig
from ..logging_setup import get_logger
from ..storage import Storage

log = get_logger("ingestion.impact")


def run_impact_mapping(cfg: AppConfig, storage: Storage, ai: AIClient) -> dict[str, int]:
    if not cfg.ai_enabled:
        log.info("AI disabled in config — skipping impact mapping")
        return {"ok": 0, "failed": 0}

    max_items = int(cfg.ai.get("figures_max_items", 30))
    max_tokens = int(cfg.ai.get("figures_max_tokens", 400))
    symbols = cfg.symbols

    items = storage.list_unprocessed_figure_statements(max_items)
    if not items:
        log.info("No unprocessed figure statements")
        return {"ok": 0, "failed": 0}

    ok, failed = 0, 0
    for item in items:
        try:
            mapped = map_statement_impact(
                ai,
                model=cfg.figures_model,
                figure=item.get("figure", ""),
                role=item.get("role"),
                text=item.get("statement", ""),
                symbols=symbols,
                max_tokens=max_tokens,
            )
            storage.update_figure_impact(
                item["id"], mapped["affected_instruments"], mapped["why_it_matters"]
            )
            ok += 1
        except Exception as exc:  # noqa: BLE001 — isolate per-item
            failed += 1
            log.error("Impact mapping failed for %s: %s", item.get("id"), exc)

    log.info(
        "Impact mapping done: %d mapped, %d failed (model=%s)",
        ok, failed, cfg.figures_model,
    )
    return {"ok": ok, "failed": failed}

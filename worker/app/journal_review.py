"""On-demand trade-journal review (M7).

Reads all journal entries, computes exact stats, asks Claude for an honest
pattern synthesis, and stores the result in `briefings` with kind
'journal_review' (reusing that pattern — no extra table). The stored body
leads with the EXACT computed stats, then the AI interpretation, so the
numbers are never AI-fabricated.

On-demand by design: the dashboard reads the latest stored review; it has no
API to the worker (a "generate now" button would need a small backend
endpoint — noted as a future extension, not built here).
"""
from __future__ import annotations

from typing import Any

from .ai import AIClient
from .ai.journal import aggregate_journal, generate_journal_review, stats_markdown
from .config import AppConfig
from .logging_setup import get_logger
from .storage import Storage

log = get_logger("journal.review")


def run_journal_review(cfg: AppConfig, storage: Storage, ai: AIClient) -> dict[str, int]:
    if not cfg.ai_enabled:
        log.info("AI disabled in config — skipping journal review")
        return {"ok": 0, "failed": 0}

    max_entries = int(cfg.ai.get("journal_review_max_entries", 200))
    max_tokens = int(cfg.ai.get("journal_review_max_tokens", 1200))

    entries = storage.list_journal_entries(max_entries)
    stats = aggregate_journal(entries, cfg.multiplier_by_symbol)

    if stats["total"] == 0:
        log.info("No journal entries — nothing to review")
        return {"ok": 0, "failed": 0}

    review = generate_journal_review(
        ai, model=cfg.journal_review_model, stats=stats, entries=entries, max_tokens=max_tokens
    )
    if not review:
        log.error("Journal review generation returned nothing")
        return {"ok": 0, "failed": 1}

    # Body = exact stats (computed) + AI interpretation + sample-size note.
    body = stats_markdown(stats) + "\n\n" + review["content"]
    if review.get("sample_size_note"):
        body += "\n\n_Sample size:_ " + review["sample_size_note"]

    try:
        storage.insert_briefing(
            {
                "kind": "journal_review",
                "title": "Journal review",
                "body": body,
                "model": cfg.journal_review_model,
                "themes_covered": [],
                "uncertainty_note": review.get("uncertainty_note"),
            }
        )
    except Exception as exc:  # noqa: BLE001
        log.error("Storing journal review failed: %s", exc)
        return {"ok": 0, "failed": 1}

    log.info(
        "Journal review done: %d entries (%d closed, win rate %s)",
        stats["total"], stats["closed"],
        f"{stats['win_rate_pct']:.1f}%" if stats["win_rate_pct"] is not None else "n/a",
    )
    return {"ok": 1, "failed": 0}

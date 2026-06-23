"""Trade-journal review (M7 / brief §8) — on-demand pattern synthesis.

Two parts:
  - `aggregate_journal`: pure, testable stats (win rate, R-multiple stats,
    thesis-played-out rate, P&L) computed in code so the numbers are EXACT.
  - `generate_journal_review`: a Claude call that interprets the stats +
    entries into patterns and recurring mistakes. It is REQUIRED to be honest
    about sample size — with few entries, patterns are tentative, never
    certainties (CLAUDE.md §5). Quality task -> a capable model by default.
"""
from __future__ import annotations

from typing import Any

from ..risk import open_risk
from .client import AIClient

_CLOSED = {"win", "loss", "breakeven"}


def _num(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def realized_r(entry: dict[str, Any], multiplier: float) -> float | None:
    """Realized R for one entry = pnl / open_risk. None if not computable."""
    pnl = _num(entry.get("pnl"))
    e = _num(entry.get("entry_price"))
    stop = _num(entry.get("stop"))
    size = _num(entry.get("size"))
    if pnl is None or e is None or stop is None or size is None:
        return None
    risk = open_risk(e, stop, size, multiplier)
    if risk is None or risk == 0:
        return None
    return pnl / risk


def aggregate_journal(
    entries: list[dict[str, Any]], multiplier_by_symbol: dict[str, float] | None = None
) -> dict[str, Any]:
    """Exact journal statistics (no AI). Safe on an empty list."""
    mult_by = multiplier_by_symbol or {}
    total = len(entries)
    wins = losses = breakevens = 0
    thesis_tracked = thesis_true = 0
    total_pnl = 0.0
    have_pnl = False
    r_values: list[float] = []

    for e in entries:
        outcome = e.get("outcome")
        if outcome == "win":
            wins += 1
        elif outcome == "loss":
            losses += 1
        elif outcome == "breakeven":
            breakevens += 1

        tpo = e.get("thesis_played_out")
        if tpo is not None:
            thesis_tracked += 1
            if tpo:
                thesis_true += 1

        pnl = _num(e.get("pnl"))
        if pnl is not None:
            total_pnl += pnl
            have_pnl = True

        r = realized_r(e, mult_by.get(e.get("symbol"), 1.0))
        if r is not None:
            r_values.append(r)

    closed = wins + losses + breakevens
    win_rate = (wins / closed * 100.0) if closed else None
    tpo_rate = (thesis_true / thesis_tracked * 100.0) if thesis_tracked else None
    avg_r = (sum(r_values) / len(r_values)) if r_values else None

    return {
        "total": total,
        "open": total - closed,
        "closed": closed,
        "wins": wins,
        "losses": losses,
        "breakevens": breakevens,
        "win_rate_pct": win_rate,
        "thesis_tracked": thesis_tracked,
        "thesis_played_out": thesis_true,
        "thesis_played_out_rate_pct": tpo_rate,
        "r_count": len(r_values),
        "avg_r": avg_r,
        "total_pnl": total_pnl if have_pnl else None,
    }


# --- AI review --------------------------------------------------------
REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "content": {"type": "string"},
        "sample_size_note": {"type": "string"},
        "uncertainty_note": {"type": "string"},
    },
    "required": ["content", "sample_size_note", "uncertainty_note"],
    "additionalProperties": False,
}

REVIEW_SYSTEM = (
    "You review a personal trade journal for a read-only cockpit. From the "
    "exact statistics and the entries provided, synthesise: which setups/themes "
    "appear to work, recurring mistakes, and what the win rate / R-multiple / "
    "thesis-played-out numbers suggest. CRITICAL honesty rules: be explicit "
    "about SAMPLE SIZE — with few closed trades, anything you observe is a "
    "tentative hypothesis, NOT a proven edge; say so plainly in "
    "'sample_size_note'. Never present a pattern as a certainty or a "
    "prediction. Do not invent numbers — use only the stats given. Keep it "
    "tight and scannable (markdown bullets). Return JSON only."
)


def stats_markdown(stats: dict[str, Any]) -> str:
    """Deterministic, exact stats block (computed, not AI)."""
    def pct(v):
        return f"{v:.1f}%" if v is not None else "—"

    return (
        f"**Sample:** {stats['total']} entries — {stats['closed']} closed, "
        f"{stats['open']} open\n"
        f"**Win rate:** {pct(stats['win_rate_pct'])} "
        f"({stats['wins']}W / {stats['losses']}L / {stats['breakevens']}BE)\n"
        f"**Thesis played out:** {pct(stats['thesis_played_out_rate_pct'])} "
        f"({stats['thesis_played_out']}/{stats['thesis_tracked']})\n"
        f"**Avg realized R:** "
        f"{(f'{stats['avg_r']:.2f}R' if stats['avg_r'] is not None else '—')} "
        f"over {stats['r_count']} entries\n"
        f"**Total P&L:** "
        f"{(f'{stats['total_pnl']:.0f}' if stats['total_pnl'] is not None else '—')}"
    )


def _entries_for_prompt(entries: list[dict[str, Any]], limit: int = 60) -> str:
    lines = []
    for e in entries[:limit]:
        lines.append(
            f"- {e.get('symbol') or '?'} | outcome={e.get('outcome') or 'open'} "
            f"| pnl={e.get('pnl')} | thesis_played_out={e.get('thesis_played_out')} "
            f"| thesis={(e.get('thesis') or '')[:120]} "
            f"| notes={(e.get('notes') or '')[:120]}"
        )
    return "\n".join(lines) or "(no entries)"


def generate_journal_review(
    ai: AIClient,
    *,
    model: str,
    stats: dict[str, Any],
    entries: list[dict[str, Any]],
    max_tokens: int = 1200,
) -> dict[str, Any] | None:
    """Return {content, sample_size_note, uncertainty_note} or None on failure."""
    user = (
        "EXACT STATISTICS (do not alter):\n"
        + stats_markdown(stats)
        + "\n\nENTRIES:\n"
        + _entries_for_prompt(entries)
        + "\n\nWrite the review. Be explicit about sample size."
    )
    data = ai.json_call(
        model=model, system=REVIEW_SYSTEM, user=user, schema=REVIEW_SCHEMA, max_tokens=max_tokens
    )
    if not data or not data.get("content"):
        return None
    if not data.get("uncertainty_note"):
        data["uncertainty_note"] = (
            "Synthesis only — not advice. Patterns are tentative, especially "
            "with a small sample; verify before acting."
        )
    data.setdefault("sample_size_note", "")
    return data

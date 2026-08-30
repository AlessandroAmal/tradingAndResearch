"""Weekly fundamentals-history + tone ingestion.

For every single-stock instrument (decision_board entries with `fundamentals: true`):
  1. fetch the ~4-5 quarterly statements and UPSERT them into fundamentals_history
     (so the record accumulates beyond the yfinance window over time);
  2. snapshot the current valuation (P/E etc.) into valuation_snapshots (so the
     "vs its own history" percentile fills in);
  3. for the latest quarter without a tone reading, gather the free earnings-linked
     news and ask the ToneProvider (Haiku) to read the LANGUAGE — persisted so it
     becomes a testable candidate factor once enough quarters accumulate. Thin text
     → "non valutabile" (never invented).

Per-symbol isolation + retry + clear logging (CLAUDE.md). READ-ONLY; no order.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..config import AppConfig
from ..logging_setup import get_logger
from ..storage import Storage
from .retry import with_retry

log = get_logger("ingestion.fundamentals")


def _single_stocks(cfg: AppConfig) -> list[dict]:
    db_cfg = dict(cfg.raw.get("decision_board", {}) or {})
    return [i for i in (db_cfg.get("instruments", []) or []) if i.get("fundamentals")]


def _gather_texts(symbol: str, name: str) -> list[dict]:
    """Free earnings-linked headlines for the latest quarter (news bodies are thin;
    the ToneProvider honestly declares 'non valutabile' when there isn't enough)."""
    try:
        from ..decision.stock_news import recent_news
        items = recent_news(name or symbol, symbol, days=120, limit=10)
    except Exception as exc:  # noqa: BLE001
        log.warning("tone news gather failed for %s: %s", symbol, exc)
        return []
    return [{"title": n.get("title"), "body": n.get("summary") or "",
             "source": n.get("source"), "date": n.get("published_at")} for n in items]


def run_fundamentals_ingestion(cfg: AppConfig, storage: Storage, fundamentals_provider,
                               tone_provider=None) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    ok = failed = quarters_stored = tone_read = 0
    for inst in _single_stocks(cfg):
        symbol = inst.get("symbol")
        name = inst.get("name") or symbol
        try:
            quarters = with_retry(lambda s=symbol: fundamentals_provider.fetch_quarterly(s),
                                  label=f"fetch_quarterly({symbol})")
            rows = [{"symbol": symbol, "as_of": now.isoformat(), "raw": q,
                     **{k: q.get(k) for k in ("period_end", "period_label", "revenue",
                        "net_income", "gross_margin", "operating_margin", "net_margin",
                        "operating_cash_flow", "capex", "fcf", "cash", "debt", "eps")}}
                    for q in quarters if q.get("period_end")]
            if rows:
                storage.upsert_fundamentals_history(rows)
                quarters_stored += len(rows)

            # valuation snapshot (accumulates the P/E percentile over time)
            f = with_retry(lambda s=symbol: fundamentals_provider.fetch(s),
                           label=f"fetch({symbol})")
            val = (f or {}).get("valuation", {})
            storage.upsert_valuation_snapshot({
                "symbol": symbol, "as_of_date": today,
                "pe_trailing": val.get("pe_trailing"), "pe_forward": val.get("pe_forward"),
                "ps": val.get("ps"), "pb": val.get("pb")})
            ok += 1

            # tone for the latest quarter, if not already read
            if tone_provider and quarters:
                latest = quarters[0]
                pe = latest["period_end"]
                if storage.get_tone_reading(symbol, pe) is None:
                    texts = _gather_texts(symbol, name)
                    prior = (storage.get_tone_reading(symbol, quarters[1]["period_end"])
                             if len(quarters) > 1 else None)
                    reading = tone_provider.read_quarter(symbol, latest["period_label"], texts, prior)
                    storage.upsert_tone_reading(_tone_row(symbol, latest, reading, tone_provider))
                    if reading.get("evaluable"):
                        tone_read += 1
        except Exception as exc:  # noqa: BLE001 — per-symbol isolation
            failed += 1
            log.error("Fundamentals ingestion failed for %s: %s", symbol, exc)
    log.info("Fundamentals ingestion: %d ok, %d failed, %d quarters, %d tone read",
             ok, failed, quarters_stored, tone_read)
    return {"ok": ok, "failed": failed, "quarters": quarters_stored, "tone": tone_read}


def read_tone_from_transcript(storage: Storage, tone_provider, symbol: str, text: str,
                              period_label: str | None = None) -> dict:
    """Read the tone from a USER-PROVIDED transcript (when the IR file can't be
    fetched automatically). Stores the transcript, targets the matching quarter
    (or the latest), compares to the prior quarter, and upserts the reading."""
    hist = storage.get_fundamentals_history(symbol, 12)   # newest first
    target = None
    if period_label:
        target = next((h for h in hist if h.get("period_label") == period_label), None)
    if target is None:
        target = hist[0] if hist else None
    if target:
        period_end = target["period_end"]
        label = target.get("period_label") or period_label
        idx = hist.index(target)
        prior_q = hist[idx + 1] if idx + 1 < len(hist) else None
        prior = storage.get_tone_reading(symbol, prior_q["period_end"]) if prior_q else None
    else:
        from datetime import date
        period_end = date.today().isoformat()
        label = period_label or "corrente"
        prior = None
    storage.upsert_transcript({"symbol": symbol, "period_end": period_end,
                               "period_label": label, "source": "manual", "text": text})
    texts = [{"title": "Trascrizione earnings call", "body": text,
              "source": "IR (caricata)", "date": period_end}]
    reading = tone_provider.read_quarter(symbol, label, texts, prior)
    storage.upsert_tone_reading(_tone_row(symbol, {"period_end": period_end,
                                                   "period_label": label}, reading, tone_provider))
    return {"reading": reading, "period_end": period_end, "period_label": label}


def _tone_row(symbol: str, quarter: dict, reading: dict, provider) -> dict:
    return {
        "symbol": symbol, "period_end": quarter["period_end"],
        "period_label": quarter.get("period_label"),
        "evaluable": bool(reading.get("evaluable")),
        "summary": reading.get("summary"),
        "changes_vs_prior": reading.get("changes_vs_prior"),
        "guidance": reading.get("guidance"),
        "caution_confidence": reading.get("caution_confidence"),
        "themes_new": reading.get("themes_new"),
        "themes_gone": reading.get("themes_gone"),
        "sources": reading.get("sources"),
        "model": getattr(provider, "_model", None),
        "raw": reading,
    }

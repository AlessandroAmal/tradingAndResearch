"""Storage interface.

CLAUDE.md architecture: storage sits behind an interface so the dev
backend and production Supabase Postgres are interchangeable — swapping
is a config change, not a rewrite. Only the methods Phase 1 needs are
defined; later phases extend this.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Storage(Protocol):
    # --- instruments ----------------------------------------------
    def upsert_instruments(self, instruments: list[dict[str, Any]]) -> None:
        """Insert/update instruments by `symbol`."""
        ...

    def get_instrument_id(self, symbol: str) -> str | None:
        """Return the instrument UUID for a symbol, or None."""
        ...

    def list_instruments(self) -> list[dict[str, Any]]:
        ...

    # --- holdings -------------------------------------------------
    def list_holdings(self) -> list[dict[str, Any]]:
        """Return all holdings rows (at least the `symbol` column)."""
        ...

    def insert_holdings(self, rows: list[dict[str, Any]]) -> None:
        """Insert new holdings rows (including quantity/avg_price)."""
        ...

    def update_holding_metadata(self, symbol: str, metadata: dict[str, Any]) -> None:
        """Update metadata for an existing holding WITHOUT touching
        quantity/avg_price (those are user-owned and must be preserved)."""
        ...

    # --- prices ---------------------------------------------------
    def upsert_prices(self, rows: list[dict[str, Any]]) -> None:
        """Insert/update OHLCV rows (unique on instrument_id + ts)."""
        ...

    # --- events ---------------------------------------------------
    def upsert_events(self, rows: list[dict[str, Any]]) -> None:
        """Insert/update calendar events (unique on title + event_time)."""
        ...

    # --- positions (read-only tracking; manual entry) -------------
    def insert_position(self, position: dict[str, Any]) -> dict[str, Any]:
        ...

    def list_positions(self, status: str | None = None) -> list[dict[str, Any]]:
        ...

    # --- risk settings (M6; seeded from config for the dashboard) --
    def upsert_risk_settings(self, settings: dict[str, Any]) -> None:
        """Upsert the singleton risk-settings row (id = 1)."""
        ...

    def get_latest_close(self, instrument_id: str) -> float | None:
        """Latest close for an instrument (current price for P&L/breach)."""
        ...

    # --- trade journal (Phase 3 / M7) -----------------------------
    def insert_journal_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        ...

    def update_journal_entry(self, entry_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        ...

    def list_journal_entries(self, limit: int = 500) -> list[dict[str, Any]]:
        """Return journal entries (newest first) for the AI review/aggregation."""
        ...

    # --- options desk (Phase 3 / M5) ------------------------------
    def upsert_options_chain(self, rows: list[dict[str, Any]]) -> None:
        """Upsert option contracts (unique on underlying+expiry+strike+option_type)."""
        ...

    def replace_hedge_proposals(self, rows: list[dict[str, Any]]) -> None:
        """Replace the proposed-hedges set (regenerated each run)."""
        ...

    # --- news (Phase 2 / M3) --------------------------------------
    def upsert_news_items(self, rows: list[dict[str, Any]]) -> None:
        """Insert news items, deduped by `url` (ignore existing)."""
        ...

    def list_untagged_news(self, limit: int) -> list[dict[str, Any]]:
        """Return newest news items not yet AI-tagged (tagged_at IS NULL)."""
        ...

    def update_news_tags(
        self, news_id: str, themes: list[str], instruments: list[str]
    ) -> None:
        """Store AI themes/instruments and stamp tagged_at."""
        ...

    def list_recent_news(self, hours: int, limit: int) -> list[dict[str, Any]]:
        """Return recently published news (for briefing input)."""
        ...

    # --- prices / events helpers (briefing inputs) ----------------
    def get_recent_prices(self, instrument_id: str, limit: int) -> list[dict[str, Any]]:
        """Return the latest `limit` price rows (ts, close) newest-first."""
        ...

    def list_upcoming_events(self, limit: int) -> list[dict[str, Any]]:
        """Return upcoming calendar events (event_time >= now)."""
        ...

    # --- briefings (AI output) ------------------------------------
    def insert_briefing(self, briefing: dict[str, Any]) -> dict[str, Any]:
        ...

    # --- key figures (Phase 2 / M4) -------------------------------
    def upsert_figure_statements(self, rows: list[dict[str, Any]]) -> None:
        """Insert figure statements, deduped by `url` (ignore existing).

        Canonical columns: figure, role, statement (text), source, url,
        stated_at; affected_instruments/why_it_matters/processed_at filled
        by the AI impact-mapping job.
        """
        ...

    def list_unprocessed_figure_statements(self, limit: int) -> list[dict[str, Any]]:
        """Return newest statements not yet impact-mapped (processed_at IS NULL)."""
        ...

    def update_figure_impact(
        self, statement_id: str, affected_instruments: list[str], why_it_matters: str
    ) -> None:
        """Store AI impact + rationale and stamp processed_at."""
        ...

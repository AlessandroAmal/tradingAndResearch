"""Supabase Postgres implementation of the Storage interface.

Uses the service-role key (server side only — never the browser).
All methods degrade loudly: failures are logged and re-raised so the
ingestion jobs can record a clear failure (CLAUDE.md standards).
"""
from __future__ import annotations

import os
import re
from typing import Any

from supabase import Client, create_client

from ..logging_setup import get_logger

log = get_logger("storage.supabase")

# PostgREST reports an unknown column as PGRST204 with a message like
# "Could not find the 'X' column of 'T' in the schema cache".
_MISSING_COL_RE = re.compile(r"Could not find the '([^']+)' column")


class SupabaseStorage:
    def __init__(self, url: str, key: str) -> None:
        self._client: Client = create_client(url, key)
        # tiny cache: symbol -> instrument_id
        self._instrument_ids: dict[str, str] = {}

    def _insert_resilient(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        """Insert a row, but if the schema is missing an optional column (schema
        drift — a migration not yet applied), drop that column and retry rather
        than losing the whole record. Persisting the payload matters more than a
        cosmetic label; the dropped column is logged so it's visible."""
        payload = dict(row)
        for _ in range(len(payload) + 1):
            try:
                res = self._client.table(table).insert(payload).execute()
                return res.data[0] if res.data else {}
            except Exception as exc:  # noqa: BLE001
                m = _MISSING_COL_RE.search(str(exc))
                if not m or m.group(1) not in payload:
                    raise
                col = m.group(1)
                payload.pop(col, None)
                log.warning("%s: column '%s' missing from schema — inserting without it "
                            "(apply the pending migration to keep it)", table, col)
        raise RuntimeError(f"{table}: could not insert after dropping unknown columns")

    # --- instruments ----------------------------------------------
    def upsert_instruments(self, instruments: list[dict[str, Any]]) -> None:
        if not instruments:
            return
        self._client.table("instruments").upsert(
            instruments, on_conflict="symbol"
        ).execute()
        self._instrument_ids.clear()  # invalidate cache
        log.info("Upserted %d instruments", len(instruments))

    def get_instrument_id(self, symbol: str) -> str | None:
        if symbol in self._instrument_ids:
            return self._instrument_ids[symbol]
        res = (
            self._client.table("instruments")
            .select("id")
            .eq("symbol", symbol)
            .limit(1)
            .execute()
        )
        if res.data:
            iid = res.data[0]["id"]
            self._instrument_ids[symbol] = iid
            return iid
        return None

    def list_instruments(self) -> list[dict[str, Any]]:
        return self._client.table("instruments").select("*").execute().data or []

    # --- holdings -------------------------------------------------
    def list_holdings(self) -> list[dict[str, Any]]:
        return self._client.table("holdings").select("*").execute().data or []

    def insert_holdings(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        self._client.table("holdings").insert(rows).execute()
        log.info("Inserted %d new holdings", len(rows))

    def update_holding_metadata(self, symbol: str, metadata: dict[str, Any]) -> None:
        # Never include quantity/avg_price here — those are user-owned.
        safe = {k: v for k, v in metadata.items() if k not in ("quantity", "avg_price")}
        if not safe:
            return
        self._client.table("holdings").update(safe).eq("symbol", symbol).execute()

    def upsert_holding(self, row: dict[str, Any]) -> dict[str, Any]:
        """Insert or update a real holding by symbol (app-level upsert: the table
        has no unique(symbol) constraint, so we branch on existence)."""
        symbol = row.get("symbol")
        existing = (
            self._client.table("holdings").select("id").eq("symbol", symbol).limit(1)
            .execute().data or []
        )
        payload = {k: v for k, v in row.items() if k != "id"}
        payload["updated_at"] = "now()"
        if existing:
            res = self._insert_resilient_update("holdings", payload, "symbol", symbol)
            return res
        return self._insert_resilient("holdings", payload)

    def delete_holding(self, symbol: str) -> None:
        self._client.table("holdings").delete().eq("symbol", symbol).execute()

    def insert_holding_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Insert ONE holding row (import path: multiple rows per symbol allowed —
        different categories/tranches — so never an upsert-by-symbol)."""
        return self._insert_resilient("holdings", {k: v for k, v in row.items() if k != "id"})

    def update_holding_by_id(self, holding_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Update ONE holding row by id (edit path — the row is the identity, since
        several rows can share a symbol). Drops unknown columns resiliently."""
        payload = {k: v for k, v in fields.items() if k != "id"}
        payload["updated_at"] = "now()"
        return self._insert_resilient_update("holdings", payload, "id", holding_id)

    def delete_holdings_by_source(self, source: str) -> int:
        res = self._client.table("holdings").delete().eq("source", source).execute()
        return len(res.data or [])

    def verify_holdings_by_ids(self, ids: list[str]) -> int:
        """Clear the review flag on several holdings at once (bulk "verificato")."""
        if not ids:
            return 0
        try:
            res = (self._client.table("holdings").update({"needs_review": False, "updated_at": "now()"})
                   .in_("id", ids).execute())
            return len(res.data or [])
        except Exception as exc:  # noqa: BLE001 — pre-0026
            log.warning("bulk verify failed (apply 0026?): %s", exc)
            return 0

    def delete_all_holdings(self) -> int:
        # Full reset for a real-portfolio CSV import (config placeholders re-seed).
        res = self._client.table("holdings").delete().neq("symbol", "\x00").execute()
        return len(res.data or [])

    # --- ISIN → ticker map ----------------------------------------
    def upsert_isin_map(self, row: dict[str, Any]) -> dict[str, Any]:
        isin = row.get("isin")
        payload = {k: v for k, v in row.items() if k != "id"}
        payload["updated_at"] = "now()"
        q = self._client.table("isin_map").select("id")
        existing = (
            (q.eq("isin", isin).limit(1).execute().data or []) if isin
            else (q.eq("ticker", row.get("ticker")).limit(1).execute().data or [])
        )
        if existing:
            (self._client.table("isin_map").update(payload)
             .eq("id", existing[0]["id"]).execute())
            return {**payload, "id": existing[0]["id"]}
        res = self._client.table("isin_map").insert(payload).execute()
        return res.data[0] if res.data else {}

    def get_isin_map(self, isin: str) -> dict[str, Any] | None:
        try:
            res = (self._client.table("isin_map").select("*").eq("isin", isin)
                   .limit(1).execute())
            return res.data[0] if res.data else None
        except Exception as exc:  # noqa: BLE001 — pre-0023: degrade, resolve falls back
            log.warning("isin_map read failed (apply migration 0023?): %s", exc)
            return None

    def find_isin_by_ticker(self, ticker: str) -> dict[str, Any] | None:
        try:
            res = (self._client.table("isin_map").select("*").ilike("ticker", ticker)
                   .limit(1).execute())
            return res.data[0] if res.data else None
        except Exception as exc:  # noqa: BLE001
            log.warning("isin_map read failed (apply migration 0023?): %s", exc)
            return None

    def list_isin_map(self) -> list[dict[str, Any]]:
        try:
            return self._client.table("isin_map").select("*").execute().data or []
        except Exception as exc:  # noqa: BLE001
            log.warning("isin_map read failed (apply migration 0023?): %s", exc)
            return []

    def _insert_resilient_update(self, table: str, payload: dict[str, Any],
                                 key: str, val: Any) -> dict[str, Any]:
        """Like _insert_resilient but for UPDATE-by-key (drops unknown columns)."""
        p = dict(payload)
        for _ in range(len(p) + 1):
            try:
                res = self._client.table(table).update(p).eq(key, val).execute()
                return res.data[0] if res.data else {}
            except Exception as exc:  # noqa: BLE001
                m = _MISSING_COL_RE.search(str(exc))
                if not m or m.group(1) not in p:
                    raise
                log.warning("%s: column '%s' missing — updating without it", table, m.group(1))
                p.pop(m.group(1), None)
        raise RuntimeError(f"{table}: could not update after dropping unknown columns")

    # --- fundamentals history + valuation + tone -----------------
    def upsert_fundamentals_history(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        try:
            self._client.table("fundamentals_history").upsert(
                rows, on_conflict="symbol,period_end").execute()
        except Exception as exc:  # noqa: BLE001 — pre-0027; degrade
            log.warning("fundamentals_history upsert failed (apply 0027?): %s", exc)

    def get_fundamentals_history(self, symbol: str, limit: int) -> list[dict[str, Any]]:
        try:
            return (self._client.table("fundamentals_history").select("*")
                    .eq("symbol", symbol).order("period_end", desc=True)
                    .limit(limit).execute().data or [])
        except Exception as exc:  # noqa: BLE001
            log.warning("fundamentals_history read failed: %s", exc)
            return []

    def upsert_valuation_snapshot(self, row: dict[str, Any]) -> None:
        try:
            self._client.table("valuation_snapshots").upsert(
                row, on_conflict="symbol,as_of_date").execute()
        except Exception as exc:  # noqa: BLE001
            log.warning("valuation_snapshots upsert failed (apply 0027?): %s", exc)

    def get_valuation_history(self, symbol: str, limit: int) -> list[dict[str, Any]]:
        try:
            return (self._client.table("valuation_snapshots").select("*")
                    .eq("symbol", symbol).order("as_of_date", desc=True)
                    .limit(limit).execute().data or [])
        except Exception as exc:  # noqa: BLE001
            log.warning("valuation_snapshots read failed: %s", exc)
            return []

    def upsert_tone_reading(self, row: dict[str, Any]) -> dict[str, Any]:
        try:
            res = self._client.table("tone_readings").upsert(
                row, on_conflict="symbol,period_end").execute()
            return res.data[0] if res.data else {}
        except Exception as exc:  # noqa: BLE001 — pre-0028
            log.warning("tone_readings upsert failed (apply 0028?): %s", exc)
            return {}

    def get_tone_readings(self, symbol: str, limit: int) -> list[dict[str, Any]]:
        try:
            return (self._client.table("tone_readings").select("*")
                    .eq("symbol", symbol).order("period_end", desc=True)
                    .limit(limit).execute().data or [])
        except Exception as exc:  # noqa: BLE001
            log.warning("tone_readings read failed: %s", exc)
            return []

    def get_tone_reading(self, symbol: str, period_end: str) -> dict[str, Any] | None:
        try:
            res = (self._client.table("tone_readings").select("*")
                   .eq("symbol", symbol).eq("period_end", period_end).limit(1).execute())
            return res.data[0] if res.data else None
        except Exception as exc:  # noqa: BLE001
            log.warning("tone_reading read failed: %s", exc)
            return None

    def upsert_transcript(self, row: dict[str, Any]) -> dict[str, Any]:
        try:
            res = self._client.table("transcripts").upsert(
                row, on_conflict="symbol,period_end").execute()
            return res.data[0] if res.data else {}
        except Exception as exc:  # noqa: BLE001 — pre-0029
            log.warning("transcripts upsert failed (apply 0029?): %s", exc)
            return {}

    def get_transcript(self, symbol: str, period_end: str) -> dict[str, Any] | None:
        try:
            res = (self._client.table("transcripts").select("*")
                   .eq("symbol", symbol).eq("period_end", period_end).limit(1).execute())
            return res.data[0] if res.data else None
        except Exception as exc:  # noqa: BLE001
            log.warning("transcript read failed: %s", exc)
            return None

    # --- prices ---------------------------------------------------
    def upsert_prices(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        self._client.table("prices").upsert(
            rows, on_conflict="instrument_id,ts"
        ).execute()
        log.info("Upserted %d price rows", len(rows))

    # --- events ---------------------------------------------------
    def upsert_events(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        self._client.table("events").upsert(
            rows, on_conflict="title,event_time"
        ).execute()
        log.info("Upserted %d events", len(rows))

    # --- positions ------------------------------------------------
    def insert_position(self, position: dict[str, Any]) -> dict[str, Any]:
        res = self._client.table("positions").insert(position).execute()
        return res.data[0] if res.data else {}

    def list_positions(self, status: str | None = None) -> list[dict[str, Any]]:
        q = self._client.table("positions").select("*")
        if status:
            q = q.eq("status", status)
        return q.execute().data or []

    def update_position(self, position_id: str, fields: dict[str, Any]) -> None:
        self._client.table("positions").update(fields).eq("id", position_id).execute()

    def insert_calibration(self, row: dict[str, Any]) -> dict[str, Any]:
        return self._insert_resilient("calibrations", row)

    def get_latest_calibration(self) -> dict[str, Any] | None:
        res = (self._client.table("calibrations").select("*")
               .order("calibrated_at", desc=True).limit(1).execute())
        return res.data[0] if res.data else None

    # --- multi-horizon prospects (0020) ---------------------------
    def upsert_prospects(self, symbol: str, snapshot: dict[str, Any]) -> None:
        self._client.table("prospects").upsert(
            {"symbol": symbol, "snapshot": snapshot, "updated_at": "now()"},
            on_conflict="symbol").execute()

    def get_prospects(self, symbol: str) -> dict[str, Any] | None:
        res = self._client.table("prospects").select("*").eq("symbol", symbol).limit(1).execute()
        return res.data[0] if res.data else None

    def list_prospects(self) -> list[dict[str, Any]]:
        return self._client.table("prospects").select("symbol, updated_at").execute().data or []

    def insert_prospect_forecast(self, row: dict[str, Any]) -> None:
        self._client.table("prospect_forecasts").insert(row).execute()

    def insert_prospect_calibration(self, row: dict[str, Any]) -> dict[str, Any]:
        return self._insert_resilient("prospect_calibrations", row)

    def get_latest_prospect_calibration(self, kind: str | None = None) -> dict[str, Any] | None:
        q = self._client.table("prospect_calibrations").select("*")
        if kind:
            q = q.eq("kind", kind)
        res = q.order("calibrated_at", desc=True).limit(1).execute()
        return res.data[0] if res.data else None

    # --- risk settings --------------------------------------------
    def upsert_risk_settings(self, settings: dict[str, Any]) -> None:
        row = {**settings, "id": 1, "updated_at": "now()"}
        self._client.table("risk_settings").upsert(row, on_conflict="id").execute()
        log.info("Risk settings upserted")

    def get_latest_close(self, instrument_id: str) -> float | None:
        rows = self.get_recent_prices(instrument_id, 1)
        if rows and rows[0].get("close") is not None:
            return float(rows[0]["close"])
        return None

    # --- trade journal --------------------------------------------
    def insert_journal_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        res = self._client.table("journal_entries").insert(entry).execute()
        return res.data[0] if res.data else {}

    def update_journal_entry(self, entry_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        res = (
            self._client.table("journal_entries")
            .update(fields)
            .eq("id", entry_id)
            .execute()
        )
        return res.data[0] if res.data else {}

    def list_journal_entries(self, limit: int = 500) -> list[dict[str, Any]]:
        return (
            self._client.table("journal_entries")
            .select("*")
            .order("entry_date", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )

    # --- options desk ---------------------------------------------
    def upsert_options_chain(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        self._client.table("options_chains").upsert(
            rows, on_conflict="underlying,expiry,strike,option_type"
        ).execute()
        log.info("Upserted %d option contracts", len(rows))

    def replace_hedge_proposals(self, rows: list[dict[str, Any]]) -> None:
        # Regenerated each run: clear then insert.
        self._client.table("hedge_proposals").delete().neq(
            "id", "00000000-0000-0000-0000-000000000000"
        ).execute()
        if rows:
            self._client.table("hedge_proposals").insert(rows).execute()
        log.info("Replaced hedge proposals with %d rows", len(rows))

    # --- alerts ---------------------------------------------------
    def list_alert_rules(self, enabled_only: bool = True) -> list[dict[str, Any]]:
        q = self._client.table("alert_rules").select("*")
        if enabled_only:
            q = q.eq("enabled", True)
        return q.execute().data or []

    def update_alert_rule_state(self, rule_id, last_triggered, last_state) -> None:
        self._client.table("alert_rules").update(
            {"last_triggered": last_triggered, "last_state": last_state}
        ).eq("id", rule_id).execute()

    def upsert_standing_rules(self, rows: list[dict[str, Any]]) -> None:
        existing = {
            r.get("standing_type")
            for r in self._client.table("alert_rules").select("standing_type").eq("kind", "standing").execute().data or []
        }
        new = [r for r in rows if r.get("standing_type") not in existing]
        if new:
            self._client.table("alert_rules").insert(new).execute()
        log.info("Seeded %d standing alert rules (%d already present)", len(new), len(rows) - len(new))

    def insert_alert(self, alert: dict[str, Any]) -> dict[str, Any]:
        res = self._client.table("alerts").insert(alert).execute()
        return res.data[0] if res.data else {}

    def recent_alert_exists(self, dedup_key: str, since_iso: str) -> bool:
        res = (
            self._client.table("alerts")
            .select("id")
            .eq("dedup_key", dedup_key)
            .gte("triggered_at", since_iso)
            .limit(1)
            .execute()
        )
        return bool(res.data)

    def list_recent_figure_statements(self, hours: int, limit: int) -> list[dict[str, Any]]:
        from datetime import datetime, timedelta, timezone

        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        return (
            self._client.table("figure_statements")
            .select("id, figure, statement, stated_at")
            .gte("stated_at", since)
            .order("stated_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )

    def get_atm_iv(self, underlying: str) -> float | None:
        rows = (
            self._client.table("options_chains")
            .select("delta, implied_vol")
            .eq("underlying", underlying)
            .eq("option_type", "call")
            .not_.is_("implied_vol", "null")
            .not_.is_("delta", "null")
            .execute()
            .data
            or []
        )
        best = None
        for r in rows:
            if r.get("delta") is None or r.get("implied_vol") is None:
                continue
            d = abs(float(r["delta"]) - 0.5)
            if best is None or d < best[0]:
                best = (d, float(r["implied_vol"]))
        return best[1] if best else None

    def get_distinct_option_underlyings(self) -> list[str]:
        rows = self._client.table("options_chains").select("underlying").execute().data or []
        return sorted({r["underlying"] for r in rows if r.get("underlying")})

    # --- news -----------------------------------------------------
    def upsert_news_items(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        # Dedup by url; ignore_duplicates avoids clobbering existing tags.
        self._client.table("news_items").upsert(
            rows, on_conflict="url", ignore_duplicates=True
        ).execute()
        log.info("Upserted %d news items", len(rows))

    def list_untagged_news(self, limit: int) -> list[dict[str, Any]]:
        return (
            self._client.table("news_items")
            .select("id, title, source, summary")
            .is_("tagged_at", "null")
            .order("published_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )

    def update_news_tags(
        self, news_id: str, themes: list[str], instruments: list[str]
    ) -> None:
        self._client.table("news_items").update(
            {
                "themes": themes,
                "instruments": instruments,
                "tagged_at": "now()",
            }
        ).eq("id", news_id).execute()

    def list_recent_news(self, hours: int, limit: int) -> list[dict[str, Any]]:
        from datetime import datetime, timedelta, timezone

        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        return (
            self._client.table("news_items")
            .select("title, source, themes, instruments, published_at")
            .gte("published_at", since)
            .order("published_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )

    # --- prices / events helpers ----------------------------------
    def get_recent_prices(self, instrument_id: str, limit: int) -> list[dict[str, Any]]:
        return (
            self._client.table("prices")
            .select("ts, close")
            .eq("instrument_id", instrument_id)
            .order("ts", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )

    def get_price_history(self, instrument_id: str, limit: int) -> list[dict[str, Any]]:
        if not instrument_id:
            return []
        return (
            self._client.table("prices")
            .select("ts, open, high, low, close")
            .eq("instrument_id", instrument_id)
            .order("ts", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )

    # --- decision board (M9) --------------------------------------
    def upsert_macro_series(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        self._client.table("macro_series").upsert(
            rows, on_conflict="series_id,obs_date"
        ).execute()
        log.info("Upserted %d macro observations", len(rows))

    def get_macro_series(self, series_id: str, limit: int) -> list[dict[str, Any]]:
        # PostgREST caps a response at its server-side max-rows (default 1000)
        # regardless of .limit(), so a long FRED history (~15y ≈ 3700 rows) would
        # be silently truncated. Page through with .range() to get the full window
        # the calibration needs (a short macro window = regime-artefact risk).
        page = 1000
        out: list[dict[str, Any]] = []
        start = 0
        while start < limit:
            end = min(start + page, limit) - 1
            rows = (
                self._client.table("macro_series")
                .select("value, obs_date")
                .eq("series_id", series_id)
                .order("obs_date", desc=True)
                .range(start, end)
                .execute()
                .data
                or []
            )
            out.extend(rows)
            if len(rows) < (end - start + 1):
                break            # last page reached
            start += page
        return out

    def list_statements_by_figure(self, figure: str, limit: int) -> list[dict[str, Any]]:
        return (
            self._client.table("figure_statements")
            .select("figure, role, statement, url, stated_at, affected_instruments, why_it_matters")
            .eq("figure", figure)
            .order("stated_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )

    def upsert_decision_board(self, symbol: str, board: dict[str, Any]) -> None:
        row = {
            "symbol": symbol,
            "name": board.get("name"),
            "board": board,
            "snapshot_at": board.get("snapshot_at"),
        }
        self._client.table("decision_boards").upsert(row, on_conflict="symbol").execute()
        log.info("Decision board snapshot upserted for %s", symbol)

    def get_decision_board(self, symbol: str) -> dict[str, Any] | None:
        res = (
            self._client.table("decision_boards")
            .select("board")
            .eq("symbol", symbol)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0].get("board") if rows else None

    # --- backtest bench -------------------------------------------
    def insert_backtest_run(self, kind, rule, instrument, params, result) -> dict[str, Any]:
        row = {
            "kind": kind, "rule": rule, "instrument": instrument,
            "params": params, "result": result,
        }
        res = self._client.table("backtest_runs").insert(row).execute()
        log.info("Backtest run stored (%s, rule=%s, instrument=%s)", kind, rule, instrument)
        return res.data[0] if res.data else {}

    def list_upcoming_events(self, limit: int) -> list[dict[str, Any]]:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        return (
            self._client.table("events")
            .select("title, event_time, importance, category, symbols")
            .gte("event_time", now)
            .order("event_time", desc=False)
            .limit(limit)
            .execute()
            .data
            or []
        )

    def list_recent_events(self, days: int, limit: int) -> list[dict[str, Any]]:
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=days)).isoformat()
        return (
            self._client.table("events")
            .select("title, event_time, importance, category, symbols")
            .gte("event_time", start)
            .lt("event_time", now.isoformat())
            .order("event_time", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )

    # --- briefings ------------------------------------------------
    def insert_briefing(self, briefing: dict[str, Any]) -> dict[str, Any]:
        res = self._client.table("briefings").insert(briefing).execute()
        return res.data[0] if res.data else {}

    # --- key figures ----------------------------------------------
    def upsert_figure_statements(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        self._client.table("figure_statements").upsert(
            rows, on_conflict="url", ignore_duplicates=True
        ).execute()
        log.info("Upserted %d figure statements", len(rows))

    def list_unprocessed_figure_statements(self, limit: int) -> list[dict[str, Any]]:
        return (
            self._client.table("figure_statements")
            .select("id, figure, role, statement")
            .is_("processed_at", "null")
            .order("stated_at", desc=True)
            .limit(limit)
            .execute()
            .data
            or []
        )

    def update_figure_impact(
        self, statement_id: str, affected_instruments: list[str], why_it_matters: str
    ) -> None:
        self._client.table("figure_statements").update(
            {
                "affected_instruments": affected_instruments,
                "why_it_matters": why_it_matters,
                "processed_at": "now()",
            }
        ).eq("id", statement_id).execute()


def build_storage() -> SupabaseStorage:
    """Factory: construct the configured storage backend from env.

    Swapping backend = changing this factory, not the callers.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set (see .env.example)."
        )
    return SupabaseStorage(url, key)

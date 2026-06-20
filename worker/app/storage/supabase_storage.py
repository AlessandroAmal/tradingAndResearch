"""Supabase Postgres implementation of the Storage interface.

Uses the service-role key (server side only — never the browser).
All methods degrade loudly: failures are logged and re-raised so the
ingestion jobs can record a clear failure (CLAUDE.md standards).
"""
from __future__ import annotations

import os
from typing import Any

from supabase import Client, create_client

from ..logging_setup import get_logger

log = get_logger("storage.supabase")


class SupabaseStorage:
    def __init__(self, url: str, key: str) -> None:
        self._client: Client = create_client(url, key)
        # tiny cache: symbol -> instrument_id
        self._instrument_ids: dict[str, str] = {}

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

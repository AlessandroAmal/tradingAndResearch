-- =====================================================================
-- Migration 0011 — Phase 4 / M9: decision board (gold first).
-- Two new tables, both additive & idempotent. Apply after 0001–0010.
--   * macro_series   — FRED time series for the macro drivers (the ONE new
--                      feed). Distinct from `gas_fundamentals` (0001), which
--                      is the energy sub-module's metric store — no overlap.
--   * decision_boards — one assembled snapshot per instrument for the
--                      dashboard (full board kept as JSON so the UI redraws
--                      without bespoke columns; mirrors the hedge_proposals
--                      legs-as-JSON pattern from 0009).
-- Naming kept consistent with prior migrations (snake_case, *_at timestamps,
-- unique keys for upsert). No column renames anywhere → no headline/title drift.
-- =====================================================================

-- Macro driver observations (FRED: DFII10, T10YIE, DTWEXBGS, …). One row per
-- (series, date); the macro job upserts, the board reads the latest values.
create table if not exists macro_series (
    id          bigint generated always as identity primary key,
    series_id   text not null,                 -- FRED series id (e.g. DFII10)
    obs_date    date not null,                 -- observation date
    value       numeric,                       -- FRED "." (missing) stored as NULL upstream
    source      text default 'fred',
    created_at  timestamptz not null default now(),
    unique (series_id, obs_date)
);
create index if not exists idx_macro_series_id_date on macro_series (series_id, obs_date desc);

-- One decision-board snapshot per instrument (regenerated each run).
create table if not exists decision_boards (
    id           uuid primary key default gen_random_uuid(),
    symbol       text not null unique,          -- instrument symbol (e.g. GC=F)
    name         text,
    board        jsonb not null,                -- full assembled board (confluence, base_rate, implied, …)
    snapshot_at  timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);

drop trigger if exists trg_decision_boards_updated on decision_boards;
create trigger trg_decision_boards_updated before update on decision_boards
    for each row execute function set_updated_at();

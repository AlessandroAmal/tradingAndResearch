-- =====================================================================
-- Migration 0012 — Phase 4: research / backtesting bench.
-- One additive table. Last migration was 0011, so this is the next number
-- (sequential, consistent naming). No existing table is touched → no drift.
-- The full result (metrics IS/OOS gross+net, equity curve, scan distribution,
-- deflated Sharpe, bootstrap) is kept as JSON so the dashboard redraws without
-- bespoke columns (same pattern as decision_boards.board / hedge_proposals.legs).
-- Apply after 0001–0011.
-- =====================================================================

create table if not exists backtest_runs (
    id          uuid primary key default gen_random_uuid(),
    kind        text not null check (kind in ('single', 'scan')),
    rule        text,                          -- single: the rule; scan: null/csv
    instrument  text,                          -- single: the symbol; scan: null
    params      jsonb,                         -- single-run parameters
    result      jsonb not null,                -- full honest payload (NET-first, IS vs OOS, …)
    created_at  timestamptz not null default now()
);
create index if not exists idx_backtest_created on backtest_runs (created_at desc);
create index if not exists idx_backtest_kind on backtest_runs (kind, created_at desc);

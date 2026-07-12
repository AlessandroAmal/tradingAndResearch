-- =====================================================================
-- Migration 0018 — event-experiment paper positions.
-- Additive & idempotent. The controlled macro-event experiment opens
-- HYPOTHETICAL (paper) positions at several delays after a US data
-- release to MEASURE what happens — never an order. `experiment` marks
-- these so they stay SEPARATE from real positions AND from the user's
-- own manual paper positions (they must not pollute real risk/heat or
-- the review of the user's own process). Rich metadata (event, delay,
-- horizon, surprise, entry conditions, exit) lives in the existing
-- `entry_conditions` jsonb; realised P&L uses `realized_pnl` (0016).
-- Apply after 0001-0017.
-- =====================================================================

alter table positions add column if not exists experiment boolean not null default false;

create index if not exists idx_positions_experiment on positions (experiment, status);

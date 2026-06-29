-- =====================================================================
-- Migration 0015 — paper (test) positions.
-- Additive & idempotent: two columns on the existing `positions` table.
-- A paper position is HYPOTHETICAL — monitored to build the user's track
-- record. It is NEVER an order (the cockpit is read-only) and it must not
-- pollute REAL portfolio heat/risk (the UI filters on `paper`).
-- `entry_conditions` snapshots the decision-board read at entry (lean,
-- implied probability, signals) for later comparison. Apply after 0001–0014.
-- =====================================================================

alter table positions add column if not exists paper boolean not null default false;
alter table positions add column if not exists entry_conditions jsonb;

create index if not exists idx_positions_paper on positions (paper, status);

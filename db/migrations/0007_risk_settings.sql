-- =====================================================================
-- Migration 0007 — Phase 3 / M6: position & risk manager.
-- NO new columns on `positions` — M6 risk is computed live from the
-- existing fields (side, entry, stop, target, size, deadline). This adds
-- only: per-instrument contract multiplier, and a singleton settings row
-- so the (config-driven) account size + risk limits are readable by the
-- dashboard without browser storage.
-- Additive & idempotent. Apply after 0001–0006.
-- =====================================================================

-- Per-instrument point value / contract multiplier (futures/CFD/FX).
alter table instruments
    add column if not exists contract_multiplier numeric not null default 1;

-- Singleton risk-settings row (seeded from config.yaml by the worker).
-- The dashboard reads this for the sizing calculator + risk-vs-limit UI.
create table if not exists risk_settings (
    id                         smallint primary key default 1,
    base_currency              text,
    account_size               numeric,
    max_risk_per_trade_pct     numeric,
    max_portfolio_heat_pct     numeric,
    max_concurrent_positions   integer,
    max_position_deadline_days integer,
    deadline_warn_days         integer,
    updated_at                 timestamptz not null default now(),
    constraint risk_settings_singleton check (id = 1)
);

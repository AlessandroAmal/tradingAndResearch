-- =====================================================================
-- Migration 0020 — multi-horizon prospects + forecast registry + calibration.
-- Additive & idempotent. Apply after 0001-0019.
--
-- prospects            : one JSONB snapshot per instrument (the live horizon
--                        grid: options / conditional / valuation distributions).
--                        Same pattern as decision_boards — no schema churn.
-- prospect_forecasts   : the FORWARD registry. Every distribution generated is
--                        logged with its declared levels/percentiles + target
--                        date; the worker fills `outcome` when the horizon
--                        matures -> forward calibration accumulates honestly.
-- prospect_calibrations: stored calibration runs (retrospective + forward):
--                        reliability, coverage, Brier, active corrections.
-- =====================================================================

create table if not exists prospects (
    symbol       text primary key,
    snapshot     jsonb not null,
    updated_at   timestamptz not null default now()
);

create table if not exists prospect_forecasts (
    id            uuid primary key default gen_random_uuid(),
    made_at       timestamptz not null default now(),
    symbol        text not null,
    horizon_days  integer not null,
    method        text not null,          -- options | conditional | valuation
    level         numeric,                -- the level the prob refers to (nullable)
    prob_below    numeric,                -- declared P(outcome <= level)
    median        numeric,
    p16 numeric, p84 numeric, p2_5 numeric, p97_5 numeric,   -- return-space bands
    entry_price   numeric,
    target_date   date not null,
    outcome_return      numeric,          -- realised return at target_date (filled later)
    outcome_recorded_at timestamptz
);
create index if not exists idx_prospect_forecasts_due
    on prospect_forecasts (target_date) where outcome_return is null;
create index if not exists idx_prospect_forecasts_sym on prospect_forecasts (symbol, method, horizon_days);

create table if not exists prospect_calibrations (
    id             uuid primary key default gen_random_uuid(),
    calibrated_at  timestamptz not null default now(),
    kind           text not null,         -- retrospective | forward
    results        jsonb,                 -- per symbol/method/horizon: reliability, coverage, brier, n
    corrections    jsonb                  -- active dispersion corrections (if any)
);
create index if not exists idx_prospect_calibrations_at on prospect_calibrations (calibrated_at desc);

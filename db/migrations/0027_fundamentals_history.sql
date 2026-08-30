-- =====================================================================
-- Migration 0027 — quarterly fundamentals history + valuation snapshots.
-- Additive & idempotent. Apply after 0001-0026.
--
-- yfinance only exposes ~4-5 quarters of statements. We persist each quarter so
-- the history ACCUMULATES beyond that window at every (weekly) run. Valuation
-- (P/E etc.) is a point-in-time market snapshot: we accumulate it too so the
-- "vs its own history" percentile fills in over time (and feeds the Prospettive
-- 3-5y valuation placeholder). All CONTEXT — already priced, never a forecast.
-- =====================================================================

create table if not exists fundamentals_history (
    id                uuid primary key default gen_random_uuid(),
    symbol            text not null,
    period_end        date not null,            -- quarter end
    period_label      text,                     -- e.g. "2026-Q2"
    revenue           numeric,
    net_income        numeric,
    gross_margin      numeric,
    operating_margin  numeric,
    net_margin        numeric,
    operating_cash_flow numeric,
    capex             numeric,
    fcf               numeric,
    cash              numeric,
    debt              numeric,
    eps               numeric,
    source            text default 'yfinance',
    as_of             timestamptz not null default now(),
    raw               jsonb,
    unique (symbol, period_end)
);
create index if not exists idx_fundh_symbol on fundamentals_history (symbol, period_end desc);

create table if not exists valuation_snapshots (
    id           uuid primary key default gen_random_uuid(),
    symbol       text not null,
    as_of_date   date not null,                 -- one snapshot per day max
    pe_trailing  numeric,
    pe_forward   numeric,
    ps           numeric,
    pb           numeric,
    source       text default 'yfinance',
    created_at   timestamptz not null default now(),
    unique (symbol, as_of_date)
);
create index if not exists idx_valsnap_symbol on valuation_snapshots (symbol, as_of_date desc);

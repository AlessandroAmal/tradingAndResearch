-- =====================================================================
-- Migration 0009 — Phase 3 / M5: options / insurance desk.
-- options_chains (0001) already has underlying, expiry, strike, option_type,
-- bid, ask, last, volume, open_interest, implied_vol, delta, snapshot_at,
-- source (NOT NULL: underlying/expiry/strike/option_type — no drift trap).
-- We REUSE those (implied_vol gets our RECALCULATED IV) and add the missing
-- Greeks + mid, a dedup index for upsert, and a hedge-proposals table.
-- Additive & idempotent. Apply after 0001–0008.
-- =====================================================================

alter table options_chains add column if not exists gamma numeric;
alter table options_chains add column if not exists theta numeric;
alter table options_chains add column if not exists vega  numeric;
alter table options_chains add column if not exists rho   numeric;
alter table options_chains add column if not exists mid   numeric;

-- Dedup target so the job can upsert a fresh snapshot per contract.
create unique index if not exists options_chains_contract_key
    on options_chains (underlying, expiry, strike, option_type);

-- Proposed hedges per holding (protective put / collar). Analysis only —
-- never an order. Legs stored as JSON so the dashboard can redraw payoff.
create table if not exists hedge_proposals (
    id            uuid primary key default gen_random_uuid(),
    symbol        text not null,          -- the holding being hedged
    underlying    text not null,          -- traded underlying (may be a proxy ETF)
    kind          text not null check (kind in ('protective_put', 'collar')),
    expiry        date,
    legs          jsonb,                  -- [{kind, side, strike, premium, qty}]
    spot          numeric,
    cost          numeric,                -- net debit (currency)
    floor         numeric,                -- worst-case position value / floor P&L
    breakeven     numeric,
    max_gain      numeric,
    pct_covered   numeric,                -- % of the holding covered (null if qty unknown)
    note          text,
    snapshot_at   timestamptz not null default now()
);
create index if not exists idx_hedge_symbol on hedge_proposals (symbol);

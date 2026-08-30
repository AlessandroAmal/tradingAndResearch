-- =====================================================================
-- Migration 0023 — real portfolio: ISIN→ticker map + holdings enrichment.
-- Additive & idempotent. Apply after 0001-0022.
--
-- The user enters real holdings by ISIN (or ticker). ISIN→ticker resolution is
-- unreliable on free sources, so every confirmed mapping is PERSISTED here and
-- reused. Holdings gain the fields a real long-book position needs: the resolved
-- ISIN, the instrument's native currency, the buy date and a free note. Holdings
-- stay SEPARATE from trade positions (they never enter trading risk heat) but do
-- feed thematic concentration and the insurance desk.
-- =====================================================================

create table if not exists isin_map (
    id          uuid primary key default gen_random_uuid(),
    isin        text unique,                 -- nullable: ticker-only entries seeded from config
    ticker      text not null,               -- yfinance symbol
    name        text,
    currency    text,                        -- native quote currency (USD/EUR/GBP/CHF/DKK/…)
    exchange    text,
    source      text default 'manual',       -- seed | yahoo | manual
    verified    boolean not null default false,  -- true once the user confirmed the mapping
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);
create index if not exists idx_isin_map_ticker on isin_map (ticker);

-- Holdings enrichment (all nullable/defaulted → existing rows unaffected).
alter table holdings add column if not exists isin        text;
alter table holdings add column if not exists name        text;
alter table holdings add column if not exists asset_class text;
alter table holdings add column if not exists currency    text;      -- native quote currency
alter table holdings add column if not exists buy_date    date;
alter table holdings add column if not exists note        text;
create index if not exists idx_holdings_isin on holdings (isin);

-- =====================================================================
-- Migration 0002 — align instruments/holdings to brief §4 metadata.
-- Additive & idempotent (safe whether or not 0001 was already applied).
-- Apply after 0001.
-- =====================================================================

-- instruments: sleeve grouping, where-tradeable note, display-only flag.
alter table instruments add column if not exists sleeve       text;
alter table instruments add column if not exists tradeable_on text;
alter table instruments add column if not exists traded       boolean not null default true;

-- holdings: denormalised name/asset_class (holdings can reference symbols
-- outside the active universe, e.g. AVGO/VRT/NVO/SPGI/SI=F).
alter table holdings add column if not exists name        text;
alter table holdings add column if not exists asset_class text;

-- One holdings row per symbol (supports idempotent metadata refresh that
-- preserves user-entered quantity/avg_price).
create unique index if not exists holdings_symbol_key on holdings (symbol);

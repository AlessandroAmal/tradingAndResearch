-- =====================================================================
-- Migration 0024 — real-portfolio CSV import: category / status / valuation.
-- Additive & idempotent. Apply after 0001-0023.
--
-- The holdings table becomes the real long book with several rows possible per
-- symbol (same ISIN in different categories, or two tranches) — there is NO
-- unique(symbol) constraint, so imported rows are distinct records. New columns:
--   category       — Azionario | Obbligazionario | Crypto | Commodity |
--                    Immobiliare | Fondi Pensione | Altro | Portafogli Figli
--   item_type      — ETF | Stock | Obbligazione | ETC | ETN | Altro
--   status         — open | closed  (Conclusa rows import as history)
--   valuation_mode — market | manual (manual = value entered by hand, no price feed)
--   manual_value   — the hand-entered value in EUR (negative for a liability)
--   is_liability   — true for the mortgage etc. (subtracts from the totals)
-- =====================================================================

alter table holdings add column if not exists category       text;
alter table holdings add column if not exists item_type      text;
alter table holdings add column if not exists status         text default 'open';
alter table holdings add column if not exists valuation_mode text default 'market';
alter table holdings add column if not exists manual_value   numeric;
alter table holdings add column if not exists is_liability   boolean default false;
create index if not exists idx_holdings_category on holdings (category);
create index if not exists idx_holdings_status on holdings (status);

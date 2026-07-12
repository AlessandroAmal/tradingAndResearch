-- =====================================================================
-- Migration 0017 — thematic tags on instruments.
-- Additive & idempotent. `themes` powers the THEMATIC CONCENTRATION
-- warning: positions sharing a theme (e.g. AI/data-center capex) are
-- correlated, so apparent diversification is not real. Seeded from
-- config.yaml (universe[].themes). NULL = untagged. Apply after 0001-0016.
--
-- REQUIRED before the worker seeds the new book holdings (MSFT/AVGO/VRT/
-- NVO/SPGI): the seed upserts a `themes` value, so without this column the
-- instruments upsert fails.
-- =====================================================================

alter table instruments add column if not exists themes jsonb;

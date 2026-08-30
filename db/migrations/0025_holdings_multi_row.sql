-- =====================================================================
-- Migration 0025 — allow several holding rows per symbol.
-- Additive/idempotent. Apply after 0001-0024.
--
-- A real portfolio can hold the SAME instrument in several rows: two tranches
-- (Alphabet), or the same ISIN in different categories (All-World in the main
-- book and in a sub-portfolio). The original unique(symbol) constraint forbade
-- that. Dropping it lets the CSV import keep those rows separate with their real
-- ticker (no de-duplication suffix needed). Pricing keys on instrument_id.
-- =====================================================================

alter table holdings drop constraint if exists holdings_symbol_key;

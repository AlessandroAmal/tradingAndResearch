-- =====================================================================
-- Migration 0030 — currency of the holding's average cost.
-- Additive & idempotent. Apply after 0001-0029.
--
-- The user reasons ONLY in EUR: the "prezzo di carico" entered is ALWAYS in EUR,
-- even for instruments quoted in another currency (BYD in HKD, US stocks in USD,
-- NVO in DKK). Treating the cost as the quote currency gave a wrong P&L. This
-- column records the cost currency (default EUR = the account currency); the
-- valuation uses it: cost_EUR = quantity × avg_price when it's already EUR
-- (exact, no conversion), else convert at the buy-date FX.
-- =====================================================================

alter table holdings add column if not exists avg_price_currency text default 'EUR';

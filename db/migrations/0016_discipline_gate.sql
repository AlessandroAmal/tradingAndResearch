-- =====================================================================
-- Migration 0016 — discipline gate settings + realised P&L on positions.
-- Additive & idempotent. The dashboard reads the risk_settings singleton
-- for the pre-trade gate (budget caps, ATR-room threshold, set-aside
-- target); `positions.realized_pnl` is written when a position is closed
-- so the set-aside tracker and the "re-entered a losing direction" guard
-- have a real number. No existing columns touched. Apply after 0001–0015.
-- =====================================================================

-- Budget caps: max committed RISK (currency) per window + per-window mode.
alter table risk_settings add column if not exists budget_day        numeric default 100;
alter table risk_settings add column if not exists budget_week       numeric default 175;
alter table risk_settings add column if not exists budget_month      numeric default 300;
alter table risk_settings add column if not exists budget_day_mode   text default 'warn';
alter table risk_settings add column if not exists budget_week_mode  text default 'warn';
alter table risk_settings add column if not exists budget_month_mode text default 'warn';

-- Sizing-with-room threshold (stop distance must clear this × ATR).
alter table risk_settings add column if not exists stop_atr_min_multiple numeric default 1.5;

-- Profit set-aside reminder (tracking only — no money moves).
alter table risk_settings add column if not exists set_aside_per_day numeric default 100;

-- Realised P&L stamped at close (paper or real) — powers the set-aside tracker
-- and the recurring-error guards. NULL while open.
alter table positions add column if not exists realized_pnl numeric;

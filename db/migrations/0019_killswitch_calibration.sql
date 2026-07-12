-- =====================================================================
-- Migration 0019 — kill-switch settings + indicator-calibration store.
-- Additive & idempotent. Apply after 0001-0018.
--
-- (C) Kill-switch: the gate reads these from the risk_settings singleton
--     (seeded from config.yaml). Soft blocks the user set when lucid.
-- (A/B) Calibration: each explicit "recalibrate from evidence" run is
--     stored as one row — the measured IC/hit-rate results + the derived
--     per-instrument lean weights. The board reads the LATEST to label the
--     gauge "calibrata al <date>" and to weight only significant factors.
-- =====================================================================

alter table risk_settings add column if not exists killswitch_enabled       boolean default true;
alter table risk_settings add column if not exists max_consecutive_losses   integer default 3;
alter table risk_settings add column if not exists cooldown_hours           numeric default 24;

create table if not exists calibrations (
    id             uuid primary key default gen_random_uuid(),
    calibrated_at  timestamptz not null default now(),
    period_start   date,
    period_end     date,
    horizons       jsonb,        -- [1,3,5,10,15,21]
    test_count     integer,      -- factors × horizons × instruments (for deflation)
    results        jsonb,        -- per instrument -> factor -> horizon -> {ic, hit_rate, n, significant}
    weights        jsonb         -- per instrument -> factor -> weight (∝ significant OOS IC)
);
create index if not exists idx_calibrations_at on calibrations (calibrated_at desc);

-- =====================================================================
-- Migration 0021 — align calibration tables with the code payloads.
-- Additive & idempotent. Apply after 0001-0020.
--
-- The calibration runners write two columns the original 0019/0020 tables
-- never declared, so PostgREST rejected the whole insert (PGRST204) and no
-- calibration was ever stored — the dashboard showed "Nessuna calibrazione
-- ancora" even after a full run. The app now degrades gracefully (drops an
-- unknown column and still stores results/weights), but apply this to keep
-- the labels the UI reads:
--   calibrations.weight_horizon    -> which horizon's IC drove the lean weights
--   prospect_calibrations.note     -> the honest scope note shown under the table
-- =====================================================================

alter table calibrations          add column if not exists weight_horizon integer;
alter table prospect_calibrations add column if not exists note           text;

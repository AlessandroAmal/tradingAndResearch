-- =====================================================================
-- Migration 0026 — holdings "to verify / verified" state.
-- Additive & idempotent. Apply after 0001-0025.
--
-- The VERIFICARE marker must be a STATE, not fixed text in the note: rows read
-- from a screenshot (uncertain data) start needs_review = true; once the user
-- edits/confirms a row the flag clears, so the warning stays only on the rows
-- still in doubt.
-- =====================================================================

alter table holdings add column if not exists needs_review boolean default false;

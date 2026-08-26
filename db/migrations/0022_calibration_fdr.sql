-- =====================================================================
-- Migration 0022 — store the calibration's FDR summary.
-- Additive & idempotent. Apply after 0001-0021.
--
-- The indicator calibration now applies a Benjamini-Hochberg FDR correction
-- across the whole family of tests (factors × horizons × instruments) on top of
-- the block-bootstrap CI. `run_calibration` writes a small summary object
-- {family_size, fdr_threshold, fdr_q, survivors}; the app degrades gracefully
-- without this column (resilient insert drops it), but apply it to keep the
-- summary. Per-cell stats (n_effective, ic_se, p_value, significant_fdr,
-- anomalous_sign) live inside the existing `results` JSONB — no schema change.
-- =====================================================================

alter table calibrations add column if not exists fdr jsonb;

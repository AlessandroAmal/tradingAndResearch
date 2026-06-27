-- =====================================================================
-- Migration 0014 — pre-trade gate settings on the risk_settings singleton.
-- Additive & idempotent: two columns the dashboard checklist reads (seeded
-- from config.yaml -> risk.rr_min / risk.event_warn_hours). No drift: existing
-- columns untouched. Apply after 0001–0012 (0013 was never created).
-- =====================================================================

alter table risk_settings add column if not exists rr_min numeric default 1.5;
alter table risk_settings add column if not exists event_warn_hours integer default 48;

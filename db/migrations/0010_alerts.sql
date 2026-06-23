-- =====================================================================
-- Migration 0010 — Phase 4 / M8: alerts.
-- The brief §7 sketches `alerts` as RULE definitions, but 0001 actually
-- created `alerts` as a DISPATCH LOG (kind, symbol, message, severity,
-- payload, triggered_at, delivered, delivered_at). To stay consistent and
-- avoid drift, we KEEP `alerts` as the sent-alerts log and add a separate
-- `alert_rules` table for rule definitions + edge/cooldown state.
-- Additive & idempotent. Apply after 0001–0009.
-- =====================================================================

-- Rule definitions: user thresholds (price/iv) + standing toggles.
create table if not exists alert_rules (
    id               uuid primary key default gen_random_uuid(),
    kind             text not null check (kind in ('price', 'iv', 'standing')),
    standing_type    text,                          -- risk|deadline|key_figure|universe_news|iv_spike
    symbol           text,                          -- for price/iv user rules
    op               text check (op in ('above', 'below')),
    threshold        numeric,
    label            text,
    enabled          boolean not null default true,
    cooldown_seconds integer not null default 3600,
    last_triggered   timestamptz,
    last_state       boolean not null default false,
    channel          text default 'telegram',
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now()
);

-- One row per standing category (for upsert/seed + dashboard toggles).
create unique index if not exists alert_rules_standing_key
    on alert_rules (standing_type) where kind = 'standing';

-- Alerts LOG: per-item dedup key + link back to the rule that fired.
alter table alerts add column if not exists dedup_key text;
alter table alerts add column if not exists rule_id   uuid;
create index if not exists idx_alerts_dedup on alerts (dedup_key, triggered_at desc);

-- keep updated_at fresh on alert_rules
drop trigger if exists trg_alert_rules_updated on alert_rules;
create trigger trg_alert_rules_updated before update on alert_rules
    for each row execute function set_updated_at();

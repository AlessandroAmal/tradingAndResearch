-- =====================================================================
-- Migration 0029 — user-provided earnings-call transcripts.
-- Additive & idempotent. Apply after 0001-0028.
--
-- When a transcript can't be fetched automatically (IR download links are JS-
-- rendered; many names have none), the user can DOWNLOAD it from the company's IR
-- site and paste it here. The stored text feeds the ToneProvider so the tone
-- becomes evaluable — instead of only ever showing "non valutabile". The text is
-- kept so the reading can be re-run. Still a QUALITATIVE read; no score.
-- =====================================================================

create table if not exists transcripts (
    id            uuid primary key default gen_random_uuid(),
    symbol        text not null,
    period_end    date not null,
    period_label  text,
    source        text default 'manual',      -- manual | ir_auto
    text          text not null,
    created_at    timestamptz not null default now(),
    unique (symbol, period_end)
);
create index if not exists idx_transcripts_symbol on transcripts (symbol, period_end desc);

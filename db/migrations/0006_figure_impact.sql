-- =====================================================================
-- Migration 0006 — Phase 2 / M4: key-figure impact mapping.
-- figure_statements (0001) already has: figure, role, statement (text,
-- NOT NULL), url, stated_at, symbols, summary. We REUSE those for the
-- ingestion write (statement = text, stated_at = datetime) — no drift —
-- and add the new columns the AI impact mapping needs.
-- Additive & idempotent. Apply after 0001–0005.
-- =====================================================================

-- Source name (0001 had only `url`); affected instruments + one-line
-- rationale + processed marker (mirrors news_items.tagged_at).
alter table figure_statements add column if not exists source               text;
alter table figure_statements add column if not exists affected_instruments text[];
alter table figure_statements add column if not exists why_it_matters       text;
alter table figure_statements add column if not exists processed_at         timestamptz;

-- Dedup target for upsert(on_conflict=url). Must be a NON-partial unique
-- index so it can serve as the ON CONFLICT (url) arbiter (a partial index
-- only arbitrates when the same predicate is restated, which supabase-py's
-- upsert does not do). NULLs are still distinct in a unique index, so
-- multiple NULL-url rows remain allowed.
drop index if exists figure_statements_url_key;
create unique index if not exists figure_statements_url_key
    on figure_statements (url);

-- Fast lookup of not-yet-mapped statements (cost-controlled impact job).
create index if not exists idx_figures_unprocessed
    on figure_statements (stated_at desc)
    where processed_at is null;

-- Per-instrument filtering of affected_instruments[] (optional UI use).
create index if not exists idx_figures_affected
    on figure_statements using gin (affected_instruments);

-- =====================================================================
-- Migration 0004 — Phase 2 / M3: news tagging + briefings.
-- Aligns news_items/briefings to brief §7 and adds AI-tagging columns.
-- Additive & idempotent. Apply after 0001–0003.
-- =====================================================================

-- news_items: brief §7 uses title/themes[]/instruments[]; add the AI
-- tagging columns. (0001 created headline/symbols/sentiment; we keep
-- those for back-compat and use the §7 names going forward.)
alter table news_items add column if not exists title       text;
alter table news_items add column if not exists themes      text[];
alter table news_items add column if not exists instruments text[];
alter table news_items add column if not exists tagged_at   timestamptz;

-- Fast lookup of not-yet-tagged items (cost-controlled tagging job).
create index if not exists idx_news_untagged
    on news_items (published_at desc)
    where tagged_at is null;

-- Per-instrument "recent relevant news" filter (instruments[] contains ?).
create index if not exists idx_news_instruments
    on news_items using gin (instruments);

-- briefings: brief §7 = (datetime, type, content, themes_covered).
-- 0001 created kind/body/generated_at/uncertainty_note; add themes_covered.
alter table briefings add column if not exists themes_covered text[];

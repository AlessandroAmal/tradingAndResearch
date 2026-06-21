-- =====================================================================
-- Migration 0005 — reconcile news_items on `title`.
-- 0001 created a legacy `headline text NOT NULL`; 0004 added `title`.
-- The news job writes `title` only, so inserts violated headline's
-- NOT NULL (Postgres 23502). This backfills title from headline, makes
-- title the required column, then drops headline.
-- Additive & idempotent (re-running after the drop is a no-op).
-- Apply after 0004.
-- =====================================================================

do $$
begin
    if exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'news_items'
          and column_name = 'headline'
    ) then
        -- 1. Preserve any existing data: copy headline -> title where missing.
        --    headline was NOT NULL, so after this every row has a title.
        update news_items set title = headline where title is null;

        -- 2. Make title the required column (matches the old headline rule).
        alter table news_items alter column title set not null;

        -- 3. Drop the legacy column.
        alter table news_items drop column headline;
    end if;
end $$;

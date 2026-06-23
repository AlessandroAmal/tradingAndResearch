-- =====================================================================
-- Migration 0008 — Phase 3 / M7: trade journal fields.
-- journal_entries (0001) has: id, position_id, symbol, title, body, tags,
-- entry_date, created_at, updated_at (none NOT NULL except id/entry_date,
-- so no headline/title-style trap). We REUSE position_id/symbol/entry_date
-- and add the brief §7 / M7 fields with consistent names. Legacy title/body
-- remain (nullable, unused). Additive & idempotent. Apply after 0001–0007.
-- =====================================================================

alter table journal_entries add column if not exists thesis            text;
alter table journal_entries add column if not exists entry_price       numeric;
alter table journal_entries add column if not exists exit_price        numeric;
alter table journal_entries add column if not exists size              numeric;
alter table journal_entries add column if not exists stop              numeric;
alter table journal_entries add column if not exists outcome           text;   -- win|loss|breakeven|null(open)
alter table journal_entries add column if not exists pnl               numeric;
alter table journal_entries add column if not exists thesis_played_out boolean;
alter table journal_entries add column if not exists notes             text;
alter table journal_entries add column if not exists reviewed          boolean not null default false;

-- Constrain outcome to the known set (NULL allowed = still open / unfilled).
do $$
begin
    if not exists (
        select 1 from pg_constraint where conname = 'journal_entries_outcome_chk'
    ) then
        alter table journal_entries
            add constraint journal_entries_outcome_chk
            check (outcome is null or outcome in ('win', 'loss', 'breakeven'));
    end if;
end $$;

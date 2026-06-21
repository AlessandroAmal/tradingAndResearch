-- DEV ONLY — riattivare la RLS con policy prima di qualsiasi deploy (Fase 4)
-- =====================================================================
-- Disabilita la Row-Level Security su tutte le tabelle dello schema public.
-- Già applicato manualmente al database di sviluppo: questo file lo documenta
-- e lo rende riproducibile. NON eseguire in produzione.
-- =====================================================================

do $$
declare
    r record;
begin
    for r in
        select tablename from pg_tables where schemaname = 'public'
    loop
        execute format('alter table public.%I disable row level security;', r.tablename);
    end loop;
end $$;

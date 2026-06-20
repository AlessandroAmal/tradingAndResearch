-- =====================================================================
-- Trading & Research Command Center — initial schema (migration 0001)
-- Tables from brief §7. Read-only cockpit: NO order execution anywhere.
-- Target: Supabase Postgres (also valid on plain Postgres).
-- Apply: psql "$DATABASE_URL" -f db/migrations/0001_init.sql
--    or paste into the Supabase SQL editor.
-- =====================================================================

create extension if not exists "pgcrypto";  -- for gen_random_uuid()

-- ---------------------------------------------------------------------
-- instruments: the tradable/observed universe (mirrors config.universe)
-- ---------------------------------------------------------------------
create table if not exists instruments (
    id           uuid primary key default gen_random_uuid(),
    symbol       text not null unique,           -- provider ticker (e.g. yfinance)
    name         text,
    asset_class  text,                            -- equity|etf|index|fx|commodity|crypto
    exchange     text,
    currency     text default 'USD',
    is_active     boolean not null default true,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- prices: OHLCV time series per instrument (daily bars in Phase 1)
-- ---------------------------------------------------------------------
create table if not exists prices (
    id             bigint generated always as identity primary key,
    instrument_id  uuid not null references instruments(id) on delete cascade,
    ts             timestamptz not null,          -- bar timestamp (date @ 00:00 for daily)
    open           numeric,
    high           numeric,
    low            numeric,
    close          numeric,
    volume         numeric,
    source         text,                          -- provider name
    created_at     timestamptz not null default now(),
    unique (instrument_id, ts)
);
create index if not exists idx_prices_instrument_ts on prices (instrument_id, ts desc);

-- ---------------------------------------------------------------------
-- holdings: currently owned long-term positions (NOT trade setups)
-- ---------------------------------------------------------------------
create table if not exists holdings (
    id             uuid primary key default gen_random_uuid(),
    instrument_id  uuid references instruments(id) on delete set null,
    symbol         text not null,                 -- denormalised for resilience
    quantity       numeric not null,
    avg_price      numeric,
    source         text default 'config',         -- config|csv|directa|manual
    updated_at     timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- positions: manually-entered trade setups (read-only tracking)
-- Business rule: deadline must be within max_position_deadline_days.
-- ---------------------------------------------------------------------
create table if not exists positions (
    id             uuid primary key default gen_random_uuid(),
    instrument_id  uuid references instruments(id) on delete set null,
    symbol         text not null,
    side           text not null check (side in ('long','short')),
    size           numeric not null,              -- quantity/contracts
    entry          numeric not null,
    stop           numeric,
    target         numeric,
    deadline       date,                          -- must be <= 3 weeks out (enforced in app)
    broker         text,
    thesis         text,
    status         text not null default 'open' check (status in ('open','closed','cancelled')),
    opened_at      timestamptz not null default now(),
    closed_at      timestamptz,
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now()
);
create index if not exists idx_positions_status on positions (status);

-- ---------------------------------------------------------------------
-- news_items: ingested news (AI synthesis lands in Phase 2)
-- ---------------------------------------------------------------------
create table if not exists news_items (
    id            uuid primary key default gen_random_uuid(),
    headline      text not null,
    url           text,
    source        text,
    published_at  timestamptz,
    symbols       text[],                          -- related instruments
    summary       text,                            -- AI summary (Phase 2)
    sentiment     text,                            -- AI tag (Phase 2)
    raw           jsonb,
    created_at    timestamptz not null default now(),
    unique (url)
);
create index if not exists idx_news_published on news_items (published_at desc);

-- ---------------------------------------------------------------------
-- events: economic / earnings / macro calendar (catalysts)
-- ---------------------------------------------------------------------
create table if not exists events (
    id           uuid primary key default gen_random_uuid(),
    title        text not null,
    category     text,                             -- economic|earnings|dividend|macro
    country      text,
    importance   text,                             -- low|medium|high
    event_time   timestamptz not null,
    actual       text,
    forecast     text,
    previous     text,
    symbols      text[],                           -- impacted instruments (optional)
    source       text,
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now(),
    unique (title, event_time)
);
create index if not exists idx_events_time on events (event_time);

-- ---------------------------------------------------------------------
-- figure_statements: key-figures tracker (central bankers, execs, etc.)
-- ---------------------------------------------------------------------
create table if not exists figure_statements (
    id            uuid primary key default gen_random_uuid(),
    figure        text not null,                   -- person/institution
    role          text,
    statement     text not null,
    url           text,
    stated_at     timestamptz,
    symbols       text[],
    summary       text,                            -- AI summary (Phase 2)
    created_at    timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- options_chains: options / insurance desk snapshots
-- ---------------------------------------------------------------------
create table if not exists options_chains (
    id            uuid primary key default gen_random_uuid(),
    underlying    text not null,
    expiry        date not null,
    strike        numeric not null,
    option_type   text not null check (option_type in ('call','put')),
    bid           numeric,
    ask           numeric,
    last          numeric,
    volume        numeric,
    open_interest numeric,
    implied_vol   numeric,
    delta         numeric,
    snapshot_at   timestamptz not null default now(),
    source        text
);
create index if not exists idx_options_underlying_exp on options_chains (underlying, expiry);

-- ---------------------------------------------------------------------
-- gas_fundamentals: energy/gas fundamentals tracker
-- ---------------------------------------------------------------------
create table if not exists gas_fundamentals (
    id           uuid primary key default gen_random_uuid(),
    metric       text not null,                    -- e.g. storage, lng_flows, hdd
    region       text,
    value        numeric,
    unit         text,
    observed_at  timestamptz not null,
    source       text,
    created_at   timestamptz not null default now(),
    unique (metric, region, observed_at)
);

-- ---------------------------------------------------------------------
-- alerts: rule-triggered notifications (Telegram primary — Phase 4)
-- ---------------------------------------------------------------------
create table if not exists alerts (
    id            uuid primary key default gen_random_uuid(),
    kind          text not null,                   -- price|event|risk|news
    symbol        text,
    message       text not null,
    severity      text default 'info',             -- info|warning|critical
    payload       jsonb,
    triggered_at  timestamptz not null default now(),
    delivered     boolean not null default false,
    delivered_at  timestamptz
);
create index if not exists idx_alerts_triggered on alerts (triggered_at desc);

-- ---------------------------------------------------------------------
-- journal_entries: trade journal / notes
-- ---------------------------------------------------------------------
create table if not exists journal_entries (
    id           uuid primary key default gen_random_uuid(),
    position_id  uuid references positions(id) on delete set null,
    symbol       text,
    title        text,
    body         text,
    tags         text[],
    entry_date   date not null default current_date,
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- briefings: AI-synthesised briefings (Phase 2 writes these)
-- ---------------------------------------------------------------------
create table if not exists briefings (
    id            uuid primary key default gen_random_uuid(),
    kind          text not null default 'daily',   -- daily|weekly|adhoc
    title         text,
    body          text not null,
    model         text,                            -- model id used
    symbols       text[],
    uncertainty_note text,                          -- honesty-about-edge flag (CLAUDE.md §5)
    generated_at  timestamptz not null default now(),
    created_at    timestamptz not null default now()
);

-- =====================================================================
-- updated_at trigger helper
-- =====================================================================
create or replace function set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

do $$
declare t text;
begin
    foreach t in array array['instruments','positions','events','journal_entries']
    loop
        execute format(
            'drop trigger if exists trg_%1$s_updated on %1$s;
             create trigger trg_%1$s_updated before update on %1$s
             for each row execute function set_updated_at();', t);
    end loop;
end $$;

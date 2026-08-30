-- =====================================================================
-- Migration 0028 — tone-of-communications readings (per quarter).
-- Additive & idempotent. Apply after 0001-0027.
--
-- A qualitative AI read of the LANGUAGE in a quarter's earnings comms/news
-- (guidance up/down, caution vs confidence, new/vanished themes) + how it changed
-- vs the prior quarter. Persisted so that, once enough quarters accumulate, the
-- tone becomes a TESTABLE candidate factor in the calibration — like everything
-- else. `evaluable = false` when there isn't enough accessible text (never
-- invented). NO numeric/directional score: the impact on the stock is NOT assumed.
-- =====================================================================

create table if not exists tone_readings (
    id                 uuid primary key default gen_random_uuid(),
    symbol             text not null,
    period_end         date not null,           -- quarter this reading refers to
    period_label       text,
    evaluable          boolean not null default false,
    summary            text,                    -- qualitative language read
    changes_vs_prior   text,                    -- "what changed in how they speak"
    guidance           text,                    -- raised | lowered | maintained | n/d
    caution_confidence text,                    -- more cautious | more confident | mixed | n/d
    themes_new         jsonb,                   -- themes that appeared
    themes_gone        jsonb,                   -- themes that vanished
    sources            jsonb,                   -- which texts were used
    model              text,
    as_of              timestamptz not null default now(),
    raw                jsonb,
    unique (symbol, period_end)
);
create index if not exists idx_tone_symbol on tone_readings (symbol, period_end desc);

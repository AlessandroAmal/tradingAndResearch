# Trading & Research Command Center — Phase 1

A personal, **read-only** trading & research cockpit. Phase 1 is the runnable
skeleton: config-driven universe/holdings, a Supabase Postgres store behind a
storage interface, a Python worker that ingests **prices** (yfinance) and an
**economic calendar** (Financial Modeling Prep) on a schedule, and a React +
Vite dashboard (watchlist, instrument detail with chart + indicators, upcoming
catalysts, and a manual position-entry form).

> **Read-only by design.** No order execution anywhere. Positions are *tracked*,
> not placed. Not financial advice.

## Repo layout

```
config/          # config.yaml — universe, holdings, account, risk limits (NOT hardcoded)
db/migrations/   # 0001_init.sql — schema (brief §7 tables)
worker/          # Python: providers, ingestion jobs, APScheduler, storage interface
dashboard/       # React + Vite frontend (reads Supabase; no browser storage)
.env.example     # backend/worker env template
```

> **Note:** the project brief (`trading_command_center_brief.md`) was not present
> in the repo when this was built, so the seed **universe/holdings in
> `config/config.yaml` are placeholders** — edit them to your real §4 list.

---

## Prerequisites

- Python 3.11+ and Node.js 18+
- A free [Supabase](https://supabase.com) project (Postgres)
- A free [Financial Modeling Prep](https://site.financialmodelingprep.com) API key
  (calendar). Prices via yfinance need no key.

---

## 1. Database

Apply the migrations **in order** to your Supabase project — paste each file
in `db/migrations/` into the Supabase **SQL editor**, or:

```bash
for f in db/migrations/*.sql; do
  psql "postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres" -f "$f"
done
```

> **Dev vs prod access:** Supabase's default grants let the `anon` key read/write
> these tables while Row-Level Security is disabled — fine for local dev. **Before
> any real deployment, enable RLS and add policies** (at minimum: read-all,
> insert-positions). Phase 1 ships no policies on purpose.

## 2. Configure environment

```bash
cp .env.example .env                      # worker/backend secrets
cp dashboard/.env.example dashboard/.env  # dashboard public keys
```

Fill in:
- `.env` → `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `FMP_API_KEY`
- `dashboard/.env` → `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`

The **service-role key stays in the worker only**; the dashboard uses the
**anon** key. Never commit `.env`.

## 3. Worker (Python)

```bash
cd worker
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# one-off commands:
python -m app.main seed       # seed instruments + holdings from config
python -m app.main prices     # fetch prices once (yfinance)
python -m app.main calendar   # fetch economic calendar once (FMP)

# or run the scheduler (blocking; cron cadence from config.yaml):
python -m app.main run
```

Schedules (overridable via `PRICES_CRON` / `CALENDAR_CRON` in `.env`):
- prices: every 15 min — `*/15 * * * *`
- calendar: daily 06:00 — `0 6 * * *`

Ingestion is resilient: one symbol or a down feed is logged and skipped, the
rest proceeds, and the dashboard degrades gracefully.

### Worker tests

```bash
cd worker && source .venv/bin/activate
python -m pytest
```

Covers the indicator math, the config loader/overrides, and price-ingestion
isolation. (Risk/sizing-math tests are scaffolded and skipped until Phase 3.)

## 4. Dashboard (React + Vite)

```bash
cd dashboard
npm install
npm run dev      # http://localhost:5273 (also on your LAN IP for phone use)
```

The dashboard reads from Supabase and shows:
- **Watchlist** with last price + daily change (auto-refresh every 60s)
- **Instrument detail**: candlestick chart + daily Δ/%, distance from MA20/50/200, ATR(14)
- **Next catalysts**: upcoming events with countdown
- **New position** form (instrument, side, size, entry, stop, target, deadline
  ≤ 3 weeks, broker, thesis) — saved to `positions` for tracking only.

> The Vite dev server binds to your LAN (`host: true`) so a phone can reach it.
> `npm audit` flags a dev-server-only esbuild/Vite advisory; fixing it needs a
> Vite major upgrade, deferred past Phase 1. For untrusted networks, set
> `server.host` to `localhost` in `vite.config.js`.

---

## Typical local run

```bash
# terminal 1 — worker
cd worker && source .venv/bin/activate && python -m app.main run

# terminal 2 — dashboard
cd dashboard && npm run dev
```

Then open the dashboard, pick an instrument, and watch the data populate as the
worker ingests.

## Hard rules (see CLAUDE.md)

Read-only · secrets only in `.env` · universe/holdings/risk all in config ·
every feed behind a provider interface · no browser storage · AI synthesis
(Phase 2+) must flag uncertainty.

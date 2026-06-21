# Trading & Research Command Center — Phases 1–2

A personal, **read-only** trading & research cockpit. The Python worker ingests
**prices** (yfinance), an **economic calendar** (FMP), and **news** (GDELT + RSS)
on a schedule, behind swappable provider interfaces, into Supabase Postgres; an
**AI layer** (Claude, server-side) tags news by theme/instrument and writes
morning + intraday briefings. The React + Vite dashboard shows the watchlist,
instrument detail (chart + indicators + relevant news), the AI briefing, upcoming
catalysts, and a manual position-entry form.

- **Phase 1** — market data, calendar, manual positions, dashboard skeleton.
- **Phase 2 (M3)** — news ingestion + Claude briefings + theme tagging (below).

> **Read-only by design.** No order execution anywhere. Positions are *tracked*,
> not placed. Not financial advice.

## Repo layout

```
config/          # config.yaml — universe, holdings, risk, themes, news, AI (NOT hardcoded)
db/migrations/   # 0001…0004 — schema (brief §7 tables) + news/AI columns
worker/          # Python: providers (prices/calendar/news), AI layer, jobs, scheduler, storage
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
- `.env` → `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `FMP_API_KEY`,
  and (Phase 2) `ANTHROPIC_API_KEY`
- `dashboard/.env` → `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`

The **service-role key and the Anthropic key stay in the worker only**
(Claude is called server-side); the dashboard uses the **anon** key. Never
commit `.env`.

## 3. Worker (Python)

```bash
cd worker
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# one-off commands:
python -m app.main seed              # seed instruments + holdings from config
python -m app.main prices            # fetch prices once (yfinance)
python -m app.main calendar          # fetch economic calendar once (FMP)
python -m app.main news              # fetch news once (GDELT + RSS)
python -m app.main tag               # AI-tag new news items (Claude)
python -m app.main briefing-morning  # generate a morning briefing
python -m app.main briefing-intraday # generate an intraday briefing

# or run the scheduler (blocking; cron cadence from config.yaml):
python -m app.main run
```

Schedules (overridable via env, e.g. `PRICES_CRON`, `NEWS_CRON`, …):
- prices: every 15 min — `*/15 * * * *`
- calendar: daily 06:00 — `0 6 * * *`
- news + AI tagging: every 30 min — `*/30 * * * *`
- morning briefing: daily 06:30 — `30 6 * * *`
- intraday briefings: 13:00 & 18:00 — `0 13,18 * * *`

Ingestion is resilient: one symbol, feed, or the Claude API being down is
logged and skipped, the rest proceeds, and the dashboard degrades gracefully.
If `ANTHROPIC_API_KEY` is unset the scheduler still runs prices/calendar/news
and simply skips tagging/briefings.

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
- **Instrument detail**: candlestick chart + daily Δ/%, distance from MA20/50/200,
  ATR(14), and a **"recent relevant news"** panel (AI-tagged for that instrument)
- **Briefing** panel: latest morning + intraday AI briefing, theme-tagged, with the
  uncertainty caveat always shown
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

---

## Phase 2 — Intelligence (M3: news + AI briefings)

Adds news ingestion, per-item AI tagging, and AI briefings. **Apply migration
`0004_news_ai.sql`** (in addition to 0001–0003) and set `ANTHROPIC_API_KEY`.

- **News** behind a `NewsProvider` interface: **GDELT** (free, no key) +
  configurable **RSS** feeds (`config.yaml → news.rss.feeds`). NewsAPI is
  optional and off by default. Items are deduped by url+title into `news_items`.
- **AI tagging** (cost-controlled): only *new, untagged* items are processed,
  capped at `ai.tagging_max_items` per run. Each is one cheap Claude call
  (`tagging_model`, default Haiku) returning **only** `{themes[], instruments[]}`,
  schema-constrained to the configured themes/universe — the model literally
  cannot invent a tag, and returns empty lists when unsure.
- **Briefings**: morning + intraday, built from recent tagged news + upcoming
  events + notable price moves, written to `briefings`. The system prompt
  enforces brevity, a scannable theme-tagged format, and the **honesty rule** —
  every briefing carries an `uncertainty_note` and never states outcomes as
  guaranteed (CLAUDE.md §5).

Models are configurable (`config.yaml → ai:` or `ANTHROPIC_*` env). Claude is
**only ever called server-side** in the worker.

### Rough cost for one day of AI

List-price estimate (Haiku 4.5 tagging $1/$5 per 1M in/out; Sonnet 4.6 briefings
$3/$15 per 1M). Actual cost scales with news volume.

| Workload | Volume/day | Est. cost |
|---|---|---|
| Tagging (Haiku) | ~150 items × ~250 in / ~30 out tok | ~$0.06 |
| Briefings (Sonnet) | 3 runs (1 morning + 2 intraday) × ~2.4k in / ~1.2k out | ~$0.08 |
| **Total** | | **~$0.15/day (~$5/month)** |

Even a busy day (~400 tagged items) stays well under ~$0.30/day. Levers:
`ai.tagging_max_items`, briefing frequency/length, or the Batches API (−50% on
tagging). **Verify current model pricing before relying on these numbers.**

---

## Hard rules (see CLAUDE.md)

Read-only · secrets only in `.env` · universe/holdings/risk all in config ·
every feed behind a provider interface · no browser storage · AI synthesis
(Phase 2+) must flag uncertainty.

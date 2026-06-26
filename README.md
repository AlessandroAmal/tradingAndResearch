# Trading & Research Command Center — Phases 1–4

A personal, **read-only** trading & research cockpit. The Python worker ingests
**prices** (yfinance), an **economic calendar** (FMP), and **news** (GDELT + RSS)
on a schedule, behind swappable provider interfaces, into Supabase Postgres; an
**AI layer** (Claude, server-side) tags news by theme/instrument and writes
morning + intraday briefings. The React + Vite dashboard shows the watchlist,
instrument detail (chart + indicators + relevant news), the AI briefing, upcoming
catalysts, and a manual position-entry form.

- **Phase 1** — market data, calendar, manual positions, dashboard skeleton.
- **Phase 2 (M3–M4)** — news + Claude briefings + theme tagging + key-figures tracker.
- **Phase 3 (M5–M7)** — options/insurance desk (recomputed IV/Greeks, hedge
  proposals, payoff/POP) + position & risk manager (sizing, live P&L, risk
  limits, breach flags) + trade journal with on-demand AI review.
- **Phase 4 (M8)** — Telegram alerts (standing flags + user price/IV thresholds,
  edge-triggered + cooldown).
- **Phase 4 (M9)** — decision board (gold first): FRED macro drivers + technicals +
  honest historical base rate (always shows `n`) + option-implied market odds.

> **Read-only by design.** No order execution anywhere. Positions are *tracked*,
> not placed. Not financial advice.

## Repo layout

```
config/          # config.yaml — universe, holdings, risk, themes, news, AI (NOT hardcoded)
db/migrations/   # 0001…0010 — schema (brief §7) + news/AI + key-figure + risk + journal + options + alerts
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
  (Phase 2) `ANTHROPIC_API_KEY`, and (Phase 4 alerts) `TELEGRAM_BOT_TOKEN` /
  `TELEGRAM_CHAT_ID`
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
python -m app.main figures           # fetch key-figure statements (M4)
python -m app.main impact            # AI impact-map new statements (M4)
python -m app.main risk              # print a risk report + breach flags (M6)
python -m app.main journal-review    # generate an AI trade-journal review (M7)
python -m app.main options           # chains + recomputed IV/Greeks + hedge proposals (M5)
python -m app.main alerts            # evaluate alert rules + notify via Telegram (M8)

# or run the scheduler (blocking; cron cadence from config.yaml):
python -m app.main run
```

Schedules (overridable via env, e.g. `PRICES_CRON`, `NEWS_CRON`, `FIGURES_CRON`, …):
- prices: every 15 min — `*/15 * * * *`
- calendar: daily 06:00 — `0 6 * * *`
- news + AI tagging: every 30 min — `*/30 * * * *`
- morning briefing: daily 06:30 — `30 6 * * *`
- intraday briefings: 13:00 & 18:00 — `0 13,18 * * *`
- key figures + impact mapping: every 45 min — `*/45 * * * *`
- options desk: daily 23:00 — `0 23 * * *`
- alert evaluation: every 10 min — `*/10 * * * *`

Ingestion is resilient: one symbol, feed, or the Claude API being down is
logged and skipped, the rest proceeds, and the dashboard degrades gracefully.
If `ANTHROPIC_API_KEY` is unset the scheduler still runs prices/calendar/news
and simply skips tagging/briefings.

### Worker tests

```bash
cd worker && source .venv/bin/activate
python -m pytest
```

Covers the indicator math, the config loader/overrides, ingestion isolation
(prices/news/figures), AI tagging/impact JSON parsing, and the **risk/sizing
math** (sizing, open risk, heat, R-multiple, P&L, breach detection) — the
piece the brief wants tested.

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
- **Key figures** feed: tracked figures' statements with AI-mapped affected
  instruments and a one-line "why it matters"
- **Next catalysts**: upcoming events with countdown
- **Sizing calculator** (M6): entry/stop/risk% [+ instrument] → suggested size,
  open risk, R:R — a calculator, it places nothing
- **Open positions table** (M6): live P&L, risk used vs limit, portfolio heat &
  position count vs limits, days-to-deadline, and breach badges (stop hit /
  risk over limit / deadline near)
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

## Phase 2 — Intelligence (M3 news + briefings, M4 key figures)

Adds news ingestion, per-item AI tagging, AI briefings, and a key-figures tracker.
**Apply migrations `0004`–`0006`** (in addition to 0001–0003) and set
`ANTHROPIC_API_KEY`.

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
- **Key figures (M4)** behind a `FigureSource` interface: per-figure Google News
  RSS search + optional official press feed (e.g. the Fed press feed for Powell),
  reusing the free news mechanics. Statements are deduped into `figure_statements`
  (canonical columns: `figure`, `statement`, `stated_at`, `source`, `url`). The AI
  **impact-mapping** job (cheap model, default Haiku) returns **only**
  `{affected_instruments[], why_it_matters}`, schema-constrained to the universe,
  empty when there's no clear impact, and phrased as possible influence — never a
  prediction. Figures are configurable in `config.yaml → figures:`.

Models are configurable (`config.yaml → ai:` or `ANTHROPIC_*` env). Claude is
**only ever called server-side** in the worker.

### Rough cost for one day of AI

List-price estimate (Haiku 4.5 tagging $1/$5 per 1M in/out; Sonnet 4.6 briefings
$3/$15 per 1M). Actual cost scales with news volume.

| Workload | Volume/day | Est. cost |
|---|---|---|
| Tagging (Haiku) | ~150 items × ~250 in / ~30 out tok | ~$0.06 |
| Impact mapping (Haiku) | ~80 statements × ~250 in / ~40 out tok | ~$0.04 |
| Briefings (Sonnet) | 3 runs (1 morning + 2 intraday) × ~2.4k in / ~1.2k out | ~$0.08 |
| **Total** | | **~$0.18/day (~$5–6/month)** |

Even a busy day stays well under ~$0.40/day. Levers: `ai.tagging_max_items`,
`ai.figures_max_items`, briefing frequency/length, or the Batches API (−50% on
the Haiku jobs). **Verify current model pricing before relying on these numbers.**

---

## Phase 3 — Trading desks (M5 options, M6 risk, M7 journal)

The risk manager + trade journal + options/insurance desk. **Apply migrations
`0007`–`0009`** and re-run `python -m app.main seed` (it mirrors `config.yaml`'s
account size + risk limits into the `risk_settings` row the dashboard reads — no
browser storage).

- **Risk/sizing math** (`worker/app/risk.py`, pure + fully unit-tested): sizing,
  open risk (currency + % of account), portfolio heat, R-multiple, unrealised
  P&L, and breach detection. Multipliers come from `instruments.contract_multiplier`
  (config `contract_multiplier`, default 1) so futures/CFD/FX size correctly.
- **Risk limits** in `config.yaml → risk:` — `max_risk_per_trade_pct`,
  `max_portfolio_heat_pct`, `max_concurrent_positions`, `max_position_deadline_days`,
  `deadline_warn_days`. Configurable, never hardcoded.
- **Breach detection = flags only** (no dispatch — Telegram is M8/Phase 4): stop
  hit, per-trade risk / heat / max-positions over limit, deadline near. Exposed in
  the dashboard badges and via `python -m app.main risk` (logs a report).

**Read-only:** sizing is a calculator and breaches are flags — nothing here places
or implies an order.

### Try it
```bash
# apply 0007, then (worker venv active):
python -m app.main seed     # seeds instruments multiplier + risk_settings
python -m app.main prices   # so positions have a current price for P&L/breach
# add a position in the dashboard form, then:
python -m app.main risk     # logs per-position + portfolio risk & breach flags
```
The dashboard's sizing calculator works immediately; the positions table fills in
P&L/risk once prices are ingested and a position is added.

### M7 — trade journal

- **CRUD** in the dashboard **Journal** view: add/edit entries with instrument,
  thesis, entry/exit price, size, stop, outcome (win/loss/breakeven + P&L),
  `thesis_played_out`, notes, `reviewed`. Optional link to a position pre-fills
  the fields. Stored in `journal_entries` (additive columns from `0008`; existing
  `title`/`body` left untouched — no drift).
- **On-demand AI review** (`python -m app.main journal-review`): computes EXACT
  stats in code (win rate, realized R-multiple stats, thesis-played-out rate,
  P&L) and has Claude (quality model, default Sonnet) interpret patterns &
  recurring mistakes. It is **required to be honest about sample size** — with
  few trades, patterns are tentative, never certainties. Saved to `briefings`
  with kind `journal_review`; the dashboard shows the latest.
- **On-demand by design:** the dashboard reads the latest stored review (it has
  no API to the worker). A "generate now" button would need a small backend
  endpoint — **noted as a future extension, not built**.

```bash
# add entries in the dashboard Journal view, then:
python -m app.main journal-review   # writes the latest review; the view shows it
```

**Read-only:** the journal records trades, it does not execute them.

### M5 — options / insurance desk

The most quant-heavy module. **Analysis only — PROPOSES hedges/structures, never
sends orders.** Apply migration `0009`.

- **`OptionsProvider`** (interface + yfinance impl): expiries, chain (strike,
  bid/ask, last, volume, OI), spot. Swappable for Polygon later.
- **Recomputed IV/Greeks** — Yahoo's `impliedVolatility` is **ignored**; from the
  market mid we solve IV (bisection) and derive delta/gamma/theta/vega/rho via
  Black-Scholes (`worker/app/options.py`, pure + heavily unit-tested).
- **Structures**: single leg, vertical spread, protective put, collar — each with
  payoff, breakeven, max loss/gain, R-R. **POP** is the risk-neutral probability
  *implied by option prices* — labelled as such, **not a forecast**.
- **Coverage reality:** yfinance has options only for US equities/ETFs. Macro
  exposures use configurable **proxy ETFs** (`config.yaml → options.macro_proxies`,
  e.g. `^NDX→QQQ`, `GC=F→GLD`, `NG=F→UNG`); FX/crypto/no-proxy underlyings degrade
  gracefully (skipped, logged).
- **Job** (`python -m app.main options`): for universe equities + holdings + proxies,
  fetches the first N expiries and strikes around ATM, writes `options_chains`, and
  builds per-holding **hedge proposals** (protective put + collar) with cost, floor,
  breakeven, %-covered, stored in `hedge_proposals`.
- **Dashboard "Options" view**: Chain tab (recomputed IV/Greeks table), Insurance
  tab (proposed hedge + payoff), Directional tab (build single leg / vertical →
  max loss, R-R, breakeven, POP, payoff).

> **Architecture note (future extension, not built):** the dashboard reads from
> Supabase and has no API to the worker, so the desk works on the underlyings the
> worker fetched. On-demand selection of *any* underlying/expiry with live
> structure recompute would need a small backend endpoint.

```bash
# apply 0009, then (worker venv active):
python -m app.main options   # e.g. fetches NVDA/QQQ/GLD… chains + IV/Greeks + hedges
```
Then open the dashboard **Options** view: pick NVDA → an expiry → the Chain tab
shows recomputed IV & Greeks; the Insurance tab shows a proposed put/collar for a
holding with its payoff.

**Read-only:** the desk analyses and proposes; it never sends an order.

---

## Phase 4 — Alerts (M8)

Telegram notifications for the facts/flags already in the system. **Apply
migration `0010_alerts.sql`** and re-run `python -m app.main seed` (seeds the
standing-category toggles). Set `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` in the
worker `.env` — **without them the job still runs and just skips dispatch (logged)**.

- **Notifier** behind an interface (`worker/app/notify/`): **Telegram** impl
  (token server-side); email is a prepared, OFF channel. `send()` never raises.
- **Schema reconciliation (no drift):** the brief §7 sketches `alerts` as rule
  definitions, but `0001` built it as a dispatch LOG. So `alerts` stays the
  **sent-alerts log** and a new **`alert_rules`** table holds the definitions +
  edge/cooldown state.
- **Standing rules** (toggleable, reuse existing data/flags): risk-limit / stop-hit
  (M6 flags), deadline approaching, new key-figure statements, news on a universe
  instrument (`news_items.instruments[]`), elevated ATM IV.
- **User-defined rules** (in the dashboard): price ≥/≤ X and IV ≥/≤ X on an
  instrument, saved to `alert_rules`.
- **Anti-spam:** edge-triggered + cooldown — an alert fires when the condition
  *becomes* true, then only re-fires after a configurable cooldown (per-item
  categories dedupe via the `alerts` log `dedup_key`). Every dispatch is logged.
- **Dashboard "Alert" view** (Trading → Alert): toggle standing categories, add/
  remove price/IV thresholds, and see the sent-alerts history.

Messages are factual (a breach, countdown, new statement, threshold touched) —
never a prediction. **Alerts notify; they execute nothing.**

### Try it
```bash
# apply 0010, then (worker venv active):
python -m app.main seed     # seeds the standing alert rules
# in the dashboard Alert view, add a price threshold easy to hit
# (e.g. NVDA price ≥ 1) so it triggers on the next prices run, then:
python -m app.main prices   # so there's a current price
python -m app.main alerts   # evaluates + sends to Telegram (or logs "skipped" without a token)
```

---

## Phase 4 — Decision board (M9)

A per-instrument confluence cockpit, **implemented first for gold (`GC=F`)** and
generalised by config (`decision_board.instruments` in `config.yaml`). It assembles
the context you weigh *before* a trade — **it is NOT a signal and NEVER a
prediction** (CLAUDE.md §1, §5). **Apply migration `0011_decision_board.sql`** and
set `FRED_API_KEY` in the worker `.env` ([free key](https://fredaccount.stlouisfed.org/apikeys)).

- **One new feed only — FRED** behind a `MacroProvider` interface
  (`worker/app/providers/macro/`). Series (daily, verified at build): real 10y
  yield `DFII10`, 10y breakeven `T10YIE`, broad dollar `DTWEXBGS`; the VIX driver
  reuses `^VIX` prices. Observations land in **`macro_series`**. Everything else is
  reuse: yfinance prices, the calendar, key-figures, the options desk / Black-Scholes.
- **Technicals** (`worker/app/technicals.py`, pure + tested): consecutive streak,
  position vs MA20/50/200, ATR(14), RSI(14) with **configurable** thresholds (gold
  default 80/40, **not** 70/30), range position, distance to round numbers.
- **Historical base rate** (`worker/app/base_rates.py`, pure + tested) — the honest
  core: for the current streak it reports how many times (`n`) it occurred and what
  happened next (% up, mean move). **`n` is always shown**; below a configurable
  threshold → *"campione insufficiente — nessuna conclusione"*; a never-seen streak
  → *"mai accaduto: nessuna base statistica"*, **no probability**. It does **not**
  compute a "rebound probability" (no gambler's fallacy).
- **Option-implied probabilities** (`worker/app/decision/implied.py`) on the GLD
  proxy: expected move ±% and risk-neutral P(above/below) at ~1d / ~3d / ~1m —
  labelled as the **market's odds, not a forecast**.
- **Confluence read** (`worker/app/decision/synthesis.py`, pure + tested): a
  TRANSPARENT lean. Each factor is classified bullish/bearish/neutral for the
  instrument with a **configurable weight**; macro factors reuse `supportive_when`,
  trend uses MA200-rising / MA50-falling. Aggregates to a **−100..+100 lean** with a
  qualitative label. Honesty enforced in code: it is the **alignment of current
  conditions, NOT a probability** — there is deliberately **no "X% up/down" field**;
  context factors (ATR/streak/event) never feed the lean; missing data excludes the
  factor. It also computes the **conditions↔market divergence** vs the implied odds
  (e.g. "conditions bearish but market ~neutral → maybe already priced in").
- **Assembly** (`worker/app/decision/board.py`): macro drivers + technicals + base
  rate + implied probs + confluence read + upcoming events + Powell statements → one
  snapshot per instrument in **`decision_boards`** (synthesis lives in the board JSON
  — **no new table**). Optional **non-directional** AI synthesis
  (`worker/app/ai/decision.py`) — describes tensions/uncertainty, never calls direction.
- **Dashboard "Decision board" view** (Trading → Decision board): top **Sintesi**
  section (lean + strength bar, expandable per-factor breakdown, conditions↔market
  divergence, fixed caveats), then confluence grid (colour = state only), base rate
  with `n` prominent + honest caveats, implied probabilities by horizon, optional AI
  summary, macro/events/figures context. Tooltips + Guide §9 (confluence read & why
  it is not a probability, MA200, RSI, ATR, base rate, implied probability).
- **Schema (no drift):** two additive tables in `0011`; `macro_series` is distinct
  from `gas_fundamentals`; no column renames anywhere.

### Try it
```bash
# apply 0011 and set FRED_API_KEY, then (worker venv active):
python -m app.main prices     # ensure gold + ^VIX history exists
python -m app.main macro      # pull FRED series -> macro_series
python -m app.main decision   # assemble + save the gold board snapshot
# then open the dashboard: Trading -> Decision board
```

---

## Hard rules (see CLAUDE.md)

Read-only · secrets only in `.env` · universe/holdings/risk all in config ·
every feed behind a provider interface · no browser storage · AI synthesis
(Phase 2+) must flag uncertainty.

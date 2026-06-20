# Trading & Research Command Center — Project Brief

> Hand this file to Claude Code as the project spec. Build incrementally, follow the phased plan, and **ask before adding anything that places real orders**. This is a personal-use tool.

---

## 1. Goal

Build a **single, always-updated command center** for discretionary trading (intraday + swing, positions closed within ~3 weeks) and options hedging. It centralises market data, an economic/event calendar, an AI-synthesised news feed, a key-figures tracker, an options/insurance desk, position & risk management, a trade journal, and alerts.

**What it is:** an information + risk-management cockpit — everything in one place, nothing missed, P&L and risk visible at a glance, news turned into a tight briefing.

**What it is NOT:** a predictive money-machine. Public news is priced in within milliseconds; this tool gives *organisation and discipline*, not a forecasting edge. The highest-value modules are the **calendar, risk manager, and journal** — not "more news". This is not financial advice; the user makes all decisions.

---

## 2. Principles & non-goals

- **Read-only v1.** No order execution. Positions are entered manually, imported via CSV, or (Directa only) synced via API. Do not build order placement unless explicitly asked.
- **Broker-agnostic.** The cockpit records positions regardless of broker; it does not depend on broker integration.
- **Focus over breadth.** A small, deliberate trading universe (Section 4), not "everything".
- **Risk-first.** Position sizing, per-trade and portfolio risk limits, and the 3-week/expiry clock are core, not optional.
- **Honest about edge.** Briefings synthesise and organise; they must not present predictions as certainties.
- **Privacy & secrets.** Personal tool. All API keys in environment variables / a `.env` file that is git-ignored. Never commit secrets.
- **Single-developer operable.** Must run locally for development and deploy to a small VPS for always-on operation.

---

## 3. Architecture & stack

```
                ┌─────────────────────────────────────────────┐
                │  Always-on backend worker (Python, on VPS)  │
                │  - scheduler (cron/APScheduler)             │
                │  - data ingestion jobs                      │
                │  - Claude API calls (briefings, tagging)    │
                │  - alert dispatch                           │
                └───────────────┬─────────────────────────────┘
                                │ writes/reads
                        ┌───────▼────────┐
                        │   Supabase     │  (Postgres + auth + realtime)
                        │  central store │
                        └───────▲────────┘
                                │ reads
                ┌───────────────┴─────────────────────────────┐
                │  Web dashboard (React)                       │
                │  desktop + mobile, reads from Supabase       │
                └─────────────────────────────────────────────┘

  Alerts ──► Telegram bot (and/or email)
```

- **Backend:** Python. Scheduler via APScheduler or system cron. Use well-maintained libraries (httpx/requests, pandas, supabase-py, anthropic). Each data source is an isolated ingestion module with ret/backoff and logging.
- **Storage:** Supabase (Postgres). Realtime subscriptions optional for live dashboard updates.
- **Frontend:** React (Vite or Next.js). Reads from Supabase. Responsive (usable on phone). No browser storage APIs — keep state in React/Supabase.
- **AI layer:** Anthropic Claude API, called from the backend for briefings and tagging, and on-demand from the dashboard. Keys server-side only.
- **Alerts:** Telegram bot (simple, free, push to phone). Email optional fallback.
- **Hosting:** Develop and run locally first (free, SQLite or local Supabase acceptable for dev). Deploy the worker to a small VPS (e.g. Hetzner ~€4–5/mo) once stable. Dashboard can be hosted on Vercel/Cloudflare Pages.

---

## 4. Trading universe (final)

Two separate "books":

### A. Holdings book — for the insurance/hedging desk
The user's longer-term portfolio (user-entered / editable; pre-seed with these and let the user confirm): **Alphabet (GOOGL), Microsoft (MSFT), Broadcom (AVGO), Vertiv (VRT), Novo Nordisk (NVO), S&P Global (SPGI), gold, silver, copper, crypto.** The options desk watches *this* book to propose protective puts / collars. Holdings are configurable; nothing is hardcoded as "owned".

### B. Trading universe — for active intraday/swing trades
A tight, deliberate set, each chosen because it is liquid, moves enough to trade, and reacts to the narratives the user tracks (Fed, ECB/EU, China, Trump/tariffs, Nvidia/Huang, Google/Pichai, Musk/Tesla):

**Macro core**
- **Nasdaq 100** (US Tech 100) — aggregates the whole tech/AI thesis + macro (Fed, tariffs, China). Most central instrument.
- **Gold (XAU/USD)** — Fed, real rates, risk-off, geopolitical/Trump uncertainty.
- **EUR/USD** — cleanest Fed-vs-ECB expression. Lower intraday range → better on catalysts/swing than scalping.

**Equities (tracked CEOs)**
- **NVDA** (Huang) — AI bellwether; also moves on China export controls.
- **TSLA** (Musk) — high-volatility, headline-driven.
- **GOOGL** (Pichai) — lower volatility; swing/earnings vehicle.

**China / commodities**
- **Copper** — cleanest China-growth proxy + AI/data-center demand.

**European session (optional)**
- **DAX / Euro Stoxx 50** — liquid instrument for the European morning before the US opens; reacts to ECB + global risk + China.

**Energy (kept, with dedicated fundamentals — see M5b)**
- **Natural gas** — retained ONLY because it has a structured, trackable driver set (EIA storage surprise, weather/degree-days, LNG feedgas, storage vs 5-yr, EU TTF/storage). Treated as a specialist sleeve with its own data feed, not a naked volatility bet.

**Dashboard gauge (not traded)**
- **VIX** — fear/volatility gauge to time hedges. Displayed, not traded directly (futures/ETPs have decay).

> Broker reality (informational; does not block v1): macro instruments (gold, EUR/USD, nat gas, indices, copper) are tradeable on Fineco via CFD/futures + its Knock-Out "options"; Directa offers an API for automatic position sync; Trade Republic is cheap stock/ETF only. **Standardised options on US single stocks (NVDA/GOOGL/TSLA) are not cleanly available on these brokers** — express those via CFD/equity, or use a US-options broker (e.g. IBKR) if real options are wanted. The cockpit records all of this regardless.

---

## 5. Modules

Each module lists what "done" looks like.

### M1 — Watchlist & market data
- Live/near-live prices and intraday + daily charts for all trading-universe instruments, plus holdings, plus indices and VIX.
- Day change, % change, simple technical context (e.g. distance from key MAs, ATR for range).
- **Done:** dashboard shows a watchlist that refreshes on schedule; clicking an instrument opens a detail view with chart and key stats.

### M2 — Economic & event calendar
- FOMC, ECB, key US/EU releases (CPI, PCE, NFP), China data (PMI), and earnings dates for the universe + holdings.
- Countdown to the next high-impact event; flag the impact level.
- **Done:** a calendar view + a "next catalysts" widget on the home screen.

### M3 — News & narrative feed (AI-synthesised)
- Ingest news + RSS (+ optional X). Claude condenses into a short briefing, **tagged by theme**: Fed, EU, China, Trump/tariffs, NVDA, Google, Musk.
- Generate a morning briefing and an intraday update ("what matters now" in ~10 lines), plus per-instrument relevance tags.
- **Done:** a daily briefing is generated automatically and shown on the home screen; each universe instrument has a "recent relevant news" panel.

### M4 — Key-figures tracker
- Monitor statements/actions from: **Trump, Powell (Fed), Musk, Jensen Huang, Sundar Pichai, China policy.**
- For each new item, Claude maps **which positions/instruments it could move** and how.
- **Done:** a feed of figure statements, each annotated with affected instruments and a one-line "why it matters".

### M5 — Options / insurance desk
- For a chosen underlying: pull the options chain, show IV, Greeks, and payoff/breakeven diagrams.
- **Insurance mode:** model protective puts / collars on the holdings book — cost, protection level, breakeven, % of portfolio covered.
- **Directional mode:** spreads/single legs — max loss, risk/reward, and probability-of-profit derived from IV.
- **Done:** select an instrument → see chain, Greeks, and a payoff chart; "insurance" tab proposes a hedge for a selected holding with cost and coverage.
- *Note:* options data is the hardest/most expensive feed (Section 6). Build the analytics against a single provider behind an interface so the source can be swapped.

### M5b — Natural gas fundamentals (dedicated sub-module)
The condition for keeping nat gas. Track and surface:
- **EIA weekly storage report** (Thu) — actual vs consensus, and the surprise.
- **Weather** — HDD/CDD and 6–14 day forecasts; major model-run shifts (GFS/ECMWF).
- **Storage vs 5-year average** and vs year-ago.
- **Dry gas production** (supply) and **LNG feedgas flows** (export demand).
- **EU exposure** — TTF front-month, EU storage fill % (GIE AGSI+), pipeline/geopolitical headlines.
- **Done:** a nat-gas panel showing storage surprise, degree-day trend, storage-vs-5yr, LNG feedgas, and TTF/EU storage, with the next EIA release countdown.

### M6 — Position & risk manager (core)
- Track open positions (manual entry / CSV import / Directa sync), P&L, and the **3-week / expiry clock** with alerts as expiry/deadline approaches.
- **Configurable risk settings:** account size, max risk per trade (% of account), max portfolio "heat" (sum of open risk), max concurrent positions.
- **Position-sizing calculator:** given entry, stop, and risk %, output size.
- Stop-loss tracking; alert when a stop level or risk limit is breached.
- **Done:** a positions table with live P&L, days-to-deadline, and risk used vs limits; a sizing calculator; breach alerts.

### M7 — Trade journal
- Log every trade: instrument, thesis, entry/exit, size, stop, outcome, and **whether the thesis played out**.
- Claude-assisted periodic review surfacing patterns (e.g. which setups/themes work, recurring mistakes).
- **Done:** add/edit journal entries; a review view + an AI "what your journal shows" summary on demand.

### M8 — Alerts
- Triggers: price thresholds, IV spikes, event countdowns, new key-figure statements, news on universe instruments, risk-limit breaches, nat-gas EIA release.
- Delivery: Telegram (primary), email (optional).
- **Done:** user can define alert rules; alerts fire via Telegram with a clear message.

---

## 6. Data sources (candidates)

Start on free tiers; the user can pay for a trial of real-time/options data for a few months. **Verify current availability, free-tier limits, and pricing at build time** (these change). Put each source behind an interface so it can be swapped.

| Data type | Free / dev | Paid / production |
|---|---|---|
| Equity & index prices, OHLC, intraday | yfinance, Alpha Vantage (limited) | Twelve Data, EODHD, Finnhub, Polygon |
| Forex (EUR/USD) & commodities (gold, copper, gas proxy) | yfinance, Twelve Data free | Twelve Data, EODHD, Polygon |
| Economic calendar | Financial Modeling Prep (free tier), scraping | Trading Economics, Finnhub |
| News & headlines | GDELT (free, powerful), RSS feeds, NewsAPI free | NewsAPI paid, provider news feeds |
| Macro/Fed data | FRED (free), Federal Reserve RSS/site | — |
| Key figures (X, Truth Social, press) | RSS, news mentions, official IR/press feeds | X/Twitter API (expensive) |
| Options chains, IV, Greeks | (limited free) | Polygon options, Tradier, ORATS |
| Nat-gas fundamentals | **EIA API (free, US gov)**, NOAA weather (free), **GIE AGSI+ (free, EU storage)** | LNG feedgas / specialist energy data |
| Positions (auto-sync) | — | Directa API (free, requires Directa account + agreement) |

---

## 7. Database schema (sketch)

Let Claude Code finalise, but cover at least:
- `instruments` — symbol, name, asset_class, sleeve (macro/equity/commodity/energy/gauge), tradeable_on.
- `prices` — instrument_id, timestamp, ohlc, volume.
- `holdings` — instrument_id, quantity, avg_price (user-entered).
- `positions` — instrument_id, side, size, entry, stop, target, opened_at, deadline (≤3wk / expiry), status, broker, thesis.
- `news_items` — source, url, published_at, title, summary, themes[], instruments[].
- `events` — type (FOMC/ECB/CPI/earnings/EIA…), datetime, impact, instrument_id (nullable).
- `figure_statements` — figure, source, datetime, text, affected_instruments[], why_it_matters.
- `options_chains` — instrument_id, expiry, strike, type, iv, greeks, snapshot_at.
- `gas_fundamentals` — date, eia_actual, eia_consensus, hdd, cdd, storage_vs_5yr, lng_feedgas, ttf_price, eu_storage_pct.
- `alerts` — rule, condition, last_triggered, channel.
- `journal_entries` — position_id (nullable), thesis, entry/exit, outcome, thesis_played_out (bool), notes, reviewed.
- `briefings` — datetime, type (morning/intraday), content, themes_covered.

---

## 8. AI layer (Claude API)

Used for synthesis/organisation, **never to present predictions as certainty**.

- **Briefing generation:** input = recent news + upcoming events + notable price moves → output = a short, theme-tagged briefing ("what matters now"). Request tight, scannable output.
- **Per-instrument relevance tagging:** classify each news item by theme and affected instruments.
- **Key-figure impact mapping:** for a new statement, output affected instruments + a one-line rationale.
- **Journal review:** summarise patterns across journal entries on demand.

Prompt patterns: keep system prompts explicit about format and brevity; ask for structured JSON when output maps to UI; always instruct the model to flag uncertainty and avoid stating outcomes as guaranteed. Use an appropriate current Claude model; make it configurable.

---

## 9. Phased build plan

**Phase 1 — Skeleton**
DB schema in Supabase · watchlist + market data (free provider) · economic/event calendar · manual position entry · home dashboard. Runs locally.

**Phase 2 — Intelligence**
News ingestion (GDELT/RSS/NewsAPI) · Claude briefings (morning + intraday) · theme tagging · key-figures tracker.

**Phase 3 — Trading desks**
Options/insurance desk (chain, Greeks, payoff, hedge proposals) · risk manager (sizing, limits, 3-week clock) · trade journal.

**Phase 4 — Live & specialist**
Alerts (Telegram) · nat-gas fundamentals sub-module · Directa API position sync (optional) · deploy worker to VPS · dashboard polish + mobile.

---

## 10. Open decisions (resolve during build)
- Final market-data provider after testing free tiers (Twelve Data vs EODHD vs Finnhub).
- Options-data source (Polygon vs Tradier vs ORATS) and whether the desk launches with live or delayed chains.
- Whether to enable Directa API auto-sync (needs account + agreement).
- Telegram-only vs Telegram + email for alerts.

---

## 11. Instructions to Claude Code
- Build **incrementally** following the phases; deliver a runnable Phase 1 before adding intelligence.
- **Keep it read-only.** Do not implement order execution. Ask first if execution is ever wanted.
- Put every external data source behind a small interface so providers can be swapped without touching the rest.
- All secrets in env vars / git-ignored `.env`; never commit keys.
- Prefer well-maintained libraries; add light tests around ingestion and the risk/sizing math.
- Make risk limits, account size, the trading universe, and holdings all **configurable** — no hardcoded financial assumptions.
- Log ingestion failures clearly; the dashboard should degrade gracefully if a feed is down.
- Verify current pricing/availability of any paid API before wiring it in.

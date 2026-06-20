# CLAUDE.md — Trading & Research Command Center

Project conventions and guardrails for Claude Code. **Read this before any work**, and
re-read it before each new phase. Full spec: `trading_command_center_brief.md`.

## What this is
A personal, **read-only** trading & research command center: market data, economic/event
calendar, AI-synthesised news briefings, key-figures tracker, options/insurance desk,
position & risk manager, trade journal, alerts. It is an information + risk-management
cockpit — **NOT** a predictive tool, **NOT** financial advice. The user makes all decisions.

## Hard rules (non-negotiable)
1. **READ-ONLY.** No order execution, ever. Positions are entered manually, via CSV import,
   or (Directa only) API sync. Do **NOT** implement order placement. **ASK FIRST** if
   execution is ever requested.
2. **SECRETS.** All API keys in environment variables / a git-ignored `.env`. Never commit
   secrets. Keep `.env.example` updated with placeholder keys only.
3. **CONFIGURABLE, NOT HARDCODED.** Trading universe, holdings, account size, and every risk
   limit live in config. Never hardcode financial assumptions or treat any position as
   "owned".
4. **PROVIDER INTERFACES.** Every external data source (prices, calendar, news, options, gas,
   positions) sits behind a small interface so providers can be swapped without touching the
   rest of the app.
5. **HONEST ABOUT EDGE.** AI briefings synthesise and organise; they must never present
   predictions as certainties. Always instruct the model to flag uncertainty and avoid
   stating outcomes as guaranteed.

## Build order
Follow the phased plan in the brief (§9). **Deliver a runnable Phase 1 before adding
intelligence.** Build incrementally; keep every phase working before moving on.

## Architecture
- **Backend worker:** Python. Scheduler = APScheduler (or system cron). Core libs: httpx,
  pandas, supabase-py, anthropic. Each ingestion module is isolated, with retry/backoff and
  clear logging.
- **Storage:** behind a storage interface. Dev backend (SQLite or local Supabase) and
  production Supabase Postgres are interchangeable — the swap must be a config change, not a
  rewrite.
- **Frontend:** React + Vite. Responsive and usable on a phone. **No browser storage APIs**
  (no localStorage/sessionStorage); keep state in React + the backend store.
- **AI:** Anthropic Claude API, called **server-side only** (keys never reach the browser).
  Model configurable via `.env` — a current Claude model such as Sonnet for high-volume
  briefings/tagging.
- **Alerts:** Telegram bot primary, email optional fallback.

## Engineering standards
- Prefer well-maintained libraries.
- Light tests around **ingestion** and the **risk/sizing math** — this math must be correct.
- Log ingestion failures clearly; the dashboard must degrade gracefully if a feed is down.
- **Verify current pricing/availability/free-tier limits of any external API before wiring it
  in** (they change).

## Non-goals
No order execution. No "predict the market". No hardcoded portfolio. No secrets in git.
No browser storage. No paid feed wired in without checking its current terms first.

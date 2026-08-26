"""Local control API for the dashboard (Phase 4 / M9).

The dashboard reads Supabase directly but cannot run the worker. This small
FastAPI app gives it two buttons:

  POST /refresh                      → FREE: run the non-AI data jobs (prices,
                                       macro/FRED, calendar) and rebuild the
                                       decision board(s) WITHOUT any AI call.
  POST /decision/{instrument}/ai     → PAID: run ONLY the AI synthesis on the
                                       current snapshot (optionally at a user
                                       price level) and save it.

Hard rules (CLAUDE.md): READ-ONLY (no orders); the Anthropic/Supabase keys stay
server-side; /refresh makes NO paid AI calls. Every endpoint requires a shared
secret (header `X-API-Token` == env `API_TOKEN`). Concurrency is guarded so a
slow refresh / AI run can't be triggered twice at once.

Run it with:  python -m app.main api    (or: uvicorn app.api:app)
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import options as opt
from .ai import build_ai_client
from .ai.decision import summarize_decision_board
from .config import AppConfig, load_config
from .ingestion.briefing_job import run_briefing
from .ingestion.calendar_job import run_calendar_ingestion
from .ingestion.macro_job import run_macro_ingestion
from .ingestion.prices_job import run_prices_ingestion
from .ingestion.seed import seed_universe_and_holdings
from .decision import run_decision_board
from .experiment.job import run_event_experiment
from .logging_setup import get_logger, setup_logging
from .providers.calendar import build_calendar_provider
from .providers.macro import build_macro_provider
from .providers.options import build_options_provider
from .providers.prices import build_price_provider
from .storage import build_storage

log = get_logger("api")

# Min seconds between two AI runs for the same instrument (anti-spam, cost).
AI_MIN_INTERVAL_S = int(os.getenv("API_AI_MIN_INTERVAL_S", "20"))

app = FastAPI(title="Trading Command Center — control API", version="1.0")

_origins = [
    o.strip() for o in os.getenv(
        "API_CORS_ORIGINS", "http://localhost:5273,http://localhost:5173"
    ).split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

# --- concurrency guards ----------------------------------------------
@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    # Return JSON (so the browser shows the real message, with CORS headers)
    # instead of a bare 500 that surfaces as an opaque "Failed to fetch".
    log.exception("Unhandled API error on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": f"Errore interno: {exc}"})


_refresh_lock = threading.Lock()
_ai_locks: dict[str, threading.Lock] = {}
_ai_last_run: dict[str, float] = {}
_ai_locks_guard = threading.Lock()


def _ai_lock(symbol: str) -> threading.Lock:
    with _ai_locks_guard:
        return _ai_locks.setdefault(symbol, threading.Lock())


# --- background job manager (long runs: calibrate, prospects) ---------
# Long jobs run in a daemon thread with a status the UI polls. The running flag
# is ALWAYS cleared in finally (release guaranteed even on crash), and a stale
# watchdog (STALE_SECONDS) lets a new run supersede a hung one — so a dead/hung
# run can never wedge the button forever (the old symptom: 409 "già in corso").
JOB_STALE_SECONDS = int(os.getenv("API_JOB_STALE_SECONDS", "1800"))   # 30 min
_jobs: dict[str, dict] = {}
_jobs_guard = threading.Lock()


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def job_status(name: str) -> dict[str, Any]:
    j = _jobs.get(name)
    if not j:
        return {"job": name, "state": "idle"}
    out: dict[str, Any] = {"job": name, "state": j["state"], "started_at": j.get("started_iso"),
                           "progress": j.get("progress"), "total": j.get("total"), "step": j.get("step")}
    if j["state"] == "running":
        out["elapsed_sec"] = round(time.monotonic() - j["started_mono"], 1)
        out["stale"] = out["elapsed_sec"] > JOB_STALE_SECONDS
    else:
        out["finished_at"] = j.get("finished_iso")
        out["duration_sec"] = j.get("duration_sec")
        if j["state"] == "done":
            out["result"] = j.get("result")
        if j["state"] == "error":
            out["error"] = j.get("error")
    return out


def start_job(name: str, fn) -> dict[str, Any]:
    """Start `fn(progress)` in a daemon thread unless a fresh run is already going.
    `fn` receives a progress(done, total, step) callback. Returns the status."""
    with _jobs_guard:
        cur = _jobs.get(name)
        if cur and cur["state"] == "running" and (time.monotonic() - cur["started_mono"]) < JOB_STALE_SECONDS:
            return {**job_status(name), "started": False}   # a fresh run is already in progress
        _jobs[name] = {"state": "running", "started_mono": time.monotonic(),
                       "started_iso": _now_iso(), "progress": 0, "total": None, "step": None}

    def _progress(done: int, total: int | None = None, step: str | None = None) -> None:
        j = _jobs.get(name)
        if j and j["state"] == "running":
            j["progress"], j["total"], j["step"] = done, total, step

    def _run() -> None:
        t0 = time.monotonic()
        try:
            result = fn(_progress)
            j = _jobs.get(name, {})
            j.update(state="done", result=result, finished_iso=_now_iso(),
                     duration_sec=round(time.monotonic() - t0, 1))
        except Exception as exc:  # noqa: BLE001 — record, never wedge the slot
            log.exception("Job %s failed: %s", name, exc)
            j = _jobs.get(name, {})
            j.update(state="error", error=str(exc), finished_iso=_now_iso(),
                     duration_sec=round(time.monotonic() - t0, 1))

    threading.Thread(target=_run, name=f"job-{name}", daemon=True).start()
    return {**job_status(name), "started": True}


# --- lazy singletons (built once) ------------------------------------
_state: dict[str, Any] = {}


def _cfg() -> AppConfig:
    if "cfg" not in _state:
        _state["cfg"] = load_config()
    return _state["cfg"]


def _storage():
    if "storage" not in _state:
        _state["storage"] = build_storage()
    return _state["storage"]


# --- auth ------------------------------------------------------------
def require_token(x_api_token: str | None = Header(default=None)) -> None:
    expected = os.getenv("API_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="API_TOKEN non configurato sul server.")
    if not x_api_token or x_api_token != expected:
        raise HTTPException(status_code=401, detail="Token mancante o non valido.")


# --- models ----------------------------------------------------------
class AIRequest(BaseModel):
    level: float | None = None   # optional user price level for P(above/below)


# --- health ----------------------------------------------------------
@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "token_configured": bool(os.getenv("API_TOKEN"))}


# --- /refresh (FREE, no AI) ------------------------------------------
@app.post("/refresh", dependencies=[Depends(require_token)])
def refresh() -> dict[str, Any]:
    if not _refresh_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Aggiornamento già in corso.")
    try:
        cfg, storage = _cfg(), _storage()
        steps: dict[str, Any] = {}

        # 0) ensure instruments exist (idempotent)
        _run_step(steps, "seed", lambda: seed_universe_and_holdings(cfg, storage))

        # 1) prices
        _run_step(steps, "prices", lambda: run_prices_ingestion(
            cfg, storage, build_price_provider(cfg.providers.get("prices", "yfinance"))))

        # 2) macro (FRED) — only if the decision board is enabled
        if cfg.decision_board_enabled:
            _run_step(steps, "macro", lambda: run_macro_ingestion(
                cfg, storage, build_macro_provider(cfg.macro_provider)))

        # 3) calendar/events (FMP -> seeded fallback inside the job)
        _run_step(steps, "calendar", lambda: run_calendar_ingestion(
            cfg, storage, build_calendar_provider(cfg.providers.get("calendar", "fmp"), cfg)))

        # 4) rebuild decision board WITHOUT AI (ai=None — no paid calls)
        if cfg.decision_board_enabled:
            _run_step(steps, "decision_board", lambda: run_decision_board(
                cfg, storage, build_options_provider(cfg.options_provider), ai=None))

        # 5) advance the event experiment (paper only — never an order)
        if cfg.experiment.get("enabled", False):
            _run_step(steps, "experiment", lambda: run_event_experiment(
                cfg, storage, build_price_provider(cfg.providers.get("prices", "yfinance"))))

        failed = sum(1 for s in steps.values() if s.get("status") == "error")
        log.info("Refresh complete (%d step errors)", failed)
        return {"ok": failed == 0, "ai_called": False, "steps": steps}
    finally:
        _refresh_lock.release()


def _run_step(steps: dict, name: str, fn) -> None:
    try:
        result = fn()
        steps[name] = {"status": "ok", "result": result}
    except Exception as exc:  # noqa: BLE001 — isolate, report per step
        log.error("Refresh step %s failed: %s", name, exc)
        steps[name] = {"status": "error", "error": str(exc)}


# --- /calibrate (FREE, BACKGROUND) — indicator calibration + lean weights ----
def _do_calibrate(progress) -> dict[str, Any]:
    cfg, storage = _cfg(), _storage()
    from .calibration_runner import run_calibration
    res = run_calibration(cfg, storage, build_price_provider(cfg.providers.get("prices", "yfinance")),
                          progress=progress)
    if cfg.decision_board_enabled:   # rebuild boards so the gauge picks up new weights
        run_decision_board(cfg, storage, build_options_provider(cfg.options_provider), ai=None)
    return res


@app.post("/calibrate", dependencies=[Depends(require_token)])
def calibrate() -> dict[str, Any]:
    return start_job("calibrate", _do_calibrate)


@app.get("/calibrate/status", dependencies=[Depends(require_token)])
def calibrate_status() -> dict[str, Any]:
    return job_status("calibrate")


# --- /prospects (FREE, BACKGROUND) — distributions + retro calibration -------
def _do_prospects(progress) -> dict[str, Any]:
    cfg, storage = _cfg(), _storage()
    from .prospects.runner import run_prospects
    return run_prospects(cfg, storage, build_options_provider(cfg.options_provider),
                         build_price_provider(cfg.providers.get("prices", "yfinance")), progress=progress)


@app.post("/prospects/refresh", dependencies=[Depends(require_token)])
def prospects_refresh() -> dict[str, Any]:
    return start_job("prospects", _do_prospects)


@app.get("/prospects/status", dependencies=[Depends(require_token)])
def prospects_status() -> dict[str, Any]:
    return job_status("prospects")


def _do_prospects_calibrate(progress) -> dict[str, Any]:
    cfg, storage = _cfg(), _storage()
    from .prospects.calibrate import run_retrospective_calibration
    return run_retrospective_calibration(
        cfg, storage, build_price_provider(cfg.providers.get("prices", "yfinance")), progress=progress)


@app.post("/prospects/calibrate", dependencies=[Depends(require_token)])
def prospects_calibrate() -> dict[str, Any]:
    return start_job("prospects_calibrate", _do_prospects_calibrate)


@app.get("/prospects/calibrate/status", dependencies=[Depends(require_token)])
def prospects_calibrate_status() -> dict[str, Any]:
    return job_status("prospects_calibrate")


# --- /decision/{instrument}/ai (PAID) --------------------------------
@app.post("/decision/{instrument}/ai", dependencies=[Depends(require_token)])
def decision_ai(instrument: str, body: AIRequest | None = None) -> dict[str, Any]:
    cfg, storage = _cfg(), _storage()
    if not cfg.ai_enabled:
        raise HTTPException(status_code=503, detail="Layer AI disabilitato in config.")

    lock = _ai_lock(instrument)
    if not lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Analisi AI già in corso per questo strumento.")
    try:
        last = _ai_last_run.get(instrument)
        if last is not None and (time.monotonic() - last) < AI_MIN_INTERVAL_S:
            raise HTTPException(status_code=429, detail="Analisi AI richiesta troppo di recente.")

        board = storage.get_decision_board(instrument)
        if not board:
            raise HTTPException(status_code=404, detail="Nessuno snapshot: premi prima Aggiorna.")

        level = body.level if body else None
        level_probs = _level_probs(board, level) if level else None

        try:
            ai = build_ai_client()
        except Exception as exc:  # noqa: BLE001 — missing key etc.
            raise HTTPException(status_code=503, detail=f"AI non disponibile: {exc}") from exc

        summary = summarize_decision_board(
            ai, model=cfg.briefing_model, board=board, level_probs=level_probs
        )
        if not summary:
            raise HTTPException(status_code=502, detail="La sintesi AI non ha prodotto output.")

        board["ai_summary"] = summary
        if level_probs:
            board["ai_level_probs"] = level_probs
        storage.upsert_decision_board(instrument, board)
        _ai_last_run[instrument] = time.monotonic()
        return {"ok": True, "ai_summary": summary, "level_probs": level_probs}
    finally:
        lock.release()


# --- /briefing/{kind} (PAID) -----------------------------------------
@app.post("/briefing/{kind}", dependencies=[Depends(require_token)])
def briefing(kind: str) -> dict[str, Any]:
    if kind not in ("morning", "intraday"):
        raise HTTPException(status_code=400, detail="kind deve essere 'morning' o 'intraday'.")
    cfg, storage = _cfg(), _storage()
    if not cfg.ai_enabled:
        raise HTTPException(status_code=503, detail="Layer AI disabilitato in config.")

    key = f"briefing:{kind}"
    lock = _ai_lock(key)
    if not lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Briefing già in corso.")
    try:
        last = _ai_last_run.get(key)
        if last is not None and (time.monotonic() - last) < AI_MIN_INTERVAL_S:
            raise HTTPException(status_code=429, detail="Briefing richiesto troppo di recente.")
        try:
            ai = build_ai_client()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=503, detail=f"AI non disponibile: {exc}") from exc

        res = run_briefing(cfg, storage, ai, kind)
        if not res or res.get("ok") != 1:
            raise HTTPException(status_code=502, detail="Il briefing non ha prodotto output.")
        _ai_last_run[key] = time.monotonic()
        return {"ok": True, "kind": kind}
    finally:
        lock.release()


def _level_probs(board: dict, level: float) -> dict[str, Any]:
    """REAL option-implied P(above/below) `level` per horizon, from stored ATM IV.
    Same risk-neutral math as the board — NOT a forecast."""
    implied = board.get("implied") or {}
    spot = implied.get("spot")
    r = implied.get("risk_free_rate", 0.04)
    out = []
    for h in implied.get("horizons", []):
        if not h.get("available") or not spot or not h.get("atm_iv"):
            continue
        T = max(h.get("days_to_expiry", 0), 0) / 365.0
        p_above = opt.prob_above(spot, level, T, r, h["atm_iv"])
        out.append({
            "target_days": h.get("target_days"),
            "expiry": h.get("expiry"),
            "prob_above": p_above,
            "prob_below": None if p_above is None else 1.0 - p_above,
        })
    return {"level": level, "spot": spot, "horizons": out,
            "note": "Probabilità implicite nei prezzi delle opzioni (odds del mercato), non una previsione."}


def run() -> int:
    """Entry point for `python -m app.main api` — serve with uvicorn."""
    import uvicorn

    setup_logging()
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8787"))
    if not os.getenv("API_TOKEN"):
        log.warning("API_TOKEN is not set — every request will 503 until you set it.")
    log.info("Starting control API on http://%s:%d (CORS: %s)", host, port, _origins)
    uvicorn.run(app, host=host, port=port)
    return 0

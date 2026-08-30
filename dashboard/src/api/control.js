// Control API client — the only place the dashboard talks to the worker.
// Two actions: /refresh (free, runs the non-AI data jobs) and /decision/{sym}/ai
// (paid, runs the AI synthesis). Auth via a shared token header. Every call
// returns { data, error } and never throws, like the Supabase data layer.
//
// NOTE: the token sits in the browser bundle — fine for local personal use; to
// be revisited if the dashboard is ever exposed online.
const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const API_TOKEN = import.meta.env.VITE_API_TOKEN || ''

export const apiConfigured = Boolean(API_URL && API_TOKEN)

async function post(path, body) {
  if (!apiConfigured) {
    return { data: null, error: new Error('API non configurata (VITE_API_URL / VITE_API_TOKEN)') }
  }
  try {
    const res = await fetch(`${API_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-API-Token': API_TOKEN },
      body: body ? JSON.stringify(body) : undefined,
    })
    const json = await res.json().catch(() => null)
    if (!res.ok) return { data: null, error: new Error(json?.detail || `HTTP ${res.status}`) }
    return { data: json, error: null }
  } catch (e) {
    return { data: null, error: e }
  }
}

async function get(path) {
  if (!apiConfigured) {
    return { data: null, error: new Error('API non configurata (VITE_API_URL / VITE_API_TOKEN)') }
  }
  try {
    const res = await fetch(`${API_URL}${path}`, { headers: { 'X-API-Token': API_TOKEN } })
    const json = await res.json().catch(() => null)
    if (!res.ok) return { data: null, error: new Error(json?.detail || `HTTP ${res.status}`) }
    return { data: json, error: null }
  } catch (e) {
    return { data: null, error: e }
  }
}

// FREE: refresh the non-AI data + rebuild the decision board(s).
export function refresh() {
  return post('/refresh')
}

// PAID: run the AI synthesis for one instrument (optionally at a price level).
export function generateAi(symbol, level) {
  return post(`/decision/${encodeURIComponent(symbol)}/ai`, level != null ? { level } : {})
}

// PAID: generate an AI briefing ('morning' | 'intraday') on demand.
export function generateBriefing(kind = 'intraday') {
  return post(`/briefing/${encodeURIComponent(kind)}`)
}

// FREE: recompute indicator calibration + evidence-based lean weights.
export function recalibrate() {
  return post('/calibrate')
}

// FREE: rebuild multi-horizon prospects; and its retrospective calibration.
export function refreshProspects() {
  return post('/prospects/refresh')
}
export function calibrateProspects() {
  return post('/prospects/calibrate')
}

// Real portfolio (holdings by ISIN). Resolution + save go through the worker so
// the instrument, its prices and the EUR/<ccy> FX pair are bootstrapped server-
// side; no order is ever placed. Delete removes the holding row.
export function resolveIsin(query) {
  return post('/isin/resolve', { query })
}
export function saveHolding(payload) {
  return post('/portfolio/holding', payload)
}
export function deleteHoldingApi(symbol) {
  return post('/portfolio/holding/delete', { symbol })
}
// Edit one holding by id (quantity/carico/valuta/data/nota/verificato + optional
// corrected ticker). A ticker change re-resolves + re-prices + updates isin_map.
export function editHolding(payload) {
  return post('/portfolio/holding/edit', payload)
}
// Plausibility check: declared cost vs market price on the buy date (historical).
export function checkPlausibility() {
  return post('/portfolio/plausibility')
}
// Bulk-clear the review flag (mark holdings as verified).
export function verifyHoldings(ids) {
  return post('/portfolio/holdings/verify', { ids })
}

// PAID: read the tone from a user-provided earnings-call transcript (one Haiku
// call). Use when the IR transcript can't be fetched automatically.
export function submitTranscript(symbol, text, periodLabel) {
  return post('/fundamentals/transcript', { symbol, text, period_label: periodLabel || null })
}

// Background-job status pollers (state: idle|running|done|error, elapsed_sec,
// progress/total/step, result, error, duration_sec, stale).
export function getCalibrateStatus() {
  return get('/calibrate/status')
}
export function getProspectsStatus() {
  return get('/prospects/status')
}
export function getProspectsCalibrateStatus() {
  return get('/prospects/calibrate/status')
}

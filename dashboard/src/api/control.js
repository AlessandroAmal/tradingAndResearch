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

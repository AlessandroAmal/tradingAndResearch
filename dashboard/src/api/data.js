// Data access — all Supabase reads/writes live here so the rest of the
// app is storage-agnostic. Every call returns { data, error } and never
// throws, so the UI can degrade gracefully when a feed/DB is down.
import { supabase, isConfigured } from '../lib/supabase'

const NOT_CONFIGURED = {
  data: null,
  error: new Error('Supabase not configured (set VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY)'),
}

export async function fetchInstruments() {
  if (!isConfigured) return NOT_CONFIGURED
  return supabase
    .from('instruments')
    .select('*')
    .eq('is_active', true)
    .order('symbol', { ascending: true })
}

export async function fetchPrices(instrumentId, limit = 250) {
  if (!isConfigured) return NOT_CONFIGURED
  // newest first for the limit, caller re-sorts ascending for charts
  return supabase
    .from('prices')
    .select('ts, open, high, low, close, volume')
    .eq('instrument_id', instrumentId)
    .order('ts', { ascending: false })
    .limit(limit)
}

export async function fetchUpcomingEvents(limit = 25) {
  if (!isConfigured) return NOT_CONFIGURED
  const nowIso = new Date().toISOString()
  return supabase
    .from('events')
    .select('*')
    .gte('event_time', nowIso)
    .order('event_time', { ascending: true })
    .limit(limit)
}

export async function fetchPositions(status = 'open') {
  if (!isConfigured) return NOT_CONFIGURED
  let q = supabase.from('positions').select('*').order('opened_at', { ascending: false })
  if (status) q = q.eq('status', status)
  return q
}

export async function insertPosition(position) {
  if (!isConfigured) return NOT_CONFIGURED
  return supabase.from('positions').insert(position).select().single()
}

// Latest AI briefing of a given kind ('morning' | 'intraday').
export async function fetchLatestBriefing(kind) {
  if (!isConfigured) return NOT_CONFIGURED
  return supabase
    .from('briefings')
    .select('kind, title, body, model, themes_covered, uncertainty_note, generated_at')
    .eq('kind', kind)
    .order('generated_at', { ascending: false })
    .limit(1)
    .maybeSingle()
}

// Recent news tagged as relevant to a specific instrument symbol.
export async function fetchNewsForInstrument(symbol, limit = 8) {
  if (!isConfigured) return NOT_CONFIGURED
  return supabase
    .from('news_items')
    .select('id, title, url, source, published_at, themes')
    .contains('instruments', [symbol])
    .order('published_at', { ascending: false })
    .limit(limit)
}

// Singleton risk settings (account size + limits), seeded from config.
export async function fetchRiskSettings() {
  if (!isConfigured) return NOT_CONFIGURED
  return supabase.from('risk_settings').select('*').eq('id', 1).maybeSingle()
}

// Recent key-figure statements with their AI impact mapping.
export async function fetchKeyFigures(limit = 15) {
  if (!isConfigured) return NOT_CONFIGURED
  return supabase
    .from('figure_statements')
    .select('id, figure, role, statement, source, url, stated_at, affected_instruments, why_it_matters')
    .order('stated_at', { ascending: false })
    .limit(limit)
}

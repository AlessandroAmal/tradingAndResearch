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

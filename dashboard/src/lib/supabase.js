import { createClient } from '@supabase/supabase-js'

// Browser-safe client (anon key). No service-role key ever reaches here.
// No browser storage (CLAUDE.md): disable auth persistence so the SDK
// does not touch localStorage.
const url = import.meta.env.VITE_SUPABASE_URL
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

export const isConfigured = Boolean(url && anonKey)

export const supabase = isConfigured
  ? createClient(url, anonKey, {
      auth: { persistSession: false, autoRefreshToken: false },
    })
  : null

// Small formatting helpers shared across components.

export function fmtPct(v) {
  if (v == null || Number.isNaN(v)) return '—'
  const sign = v > 0 ? '+' : ''
  return `${sign}${v.toFixed(2)}%`
}

export function fmtNum(v, digits = 2) {
  if (v == null || Number.isNaN(v)) return '—'
  return Number(v).toFixed(digits)
}

// Italian singular/plural picker: pluralize(1,'giorno','giorni') -> 'giorno'.
export function pluralize(n, sing, plur) {
  return Math.abs(n) === 1 ? sing : plur
}

// "N min/ore/giorni fa" since a past ISO timestamp — makes staleness obvious.
export function relativeTime(iso, nowMs = Date.now()) {
  const diff = nowMs - new Date(iso).getTime()
  if (Number.isNaN(diff)) return '—'
  if (diff < 0) return 'ora'
  const m = Math.floor(diff / 60000)
  const h = Math.floor(m / 60)
  const d = Math.floor(h / 24)
  if (d > 0) return `${d} ${pluralize(d, 'giorno', 'giorni')} fa`
  if (h > 0) return `${h} ${pluralize(h, 'ora', 'ore')} fa`
  if (m > 0) return `${m} min fa`
  return 'pochi secondi fa'
}

// Countdown like "2d 4h" / "3h 12m" / "8m" until a future ISO timestamp.
export function countdown(toIso, nowMs = Date.now()) {
  const diff = new Date(toIso).getTime() - nowMs
  if (Number.isNaN(diff)) return '—'
  if (diff <= 0) return 'now'
  const m = Math.floor(diff / 60000)
  const d = Math.floor(m / 1440)
  const h = Math.floor((m % 1440) / 60)
  const mm = m % 60
  if (d > 0) return `${d}d ${h}h`
  if (h > 0) return `${h}h ${mm}m`
  return `${mm}m`
}

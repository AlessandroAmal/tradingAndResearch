// Client mirror of worker/app/discipline.py — profit set-aside, committed-budget
// windows, and the 2/3 profit-giveback exit guide. READ-ONLY reminders from YOUR
// rules and realised numbers. Nothing here moves money or predicts price.
import { openRisk, unrealizedPnl } from './risk'

export const TWO_THIRDS = 2 / 3

function asDate(v) {
  if (!v) return null
  const s = String(v).slice(0, 10)
  return /^\d{4}-\d{2}-\d{2}$/.test(s) ? s : null
}
const todayISO = (nowMs = Date.now()) => new Date(nowMs).toISOString().slice(0, 10)

// --- profit set-aside tracker (#4) ---
export function setAsideToday(closedTrades, target, nowMs = Date.now()) {
  const today = todayISO(nowMs)
  let realized = 0
  for (const t of closedTrades || []) {
    if (asDate(t.closed_at) !== today) continue
    const pnl = t.realized_pnl
    if (pnl != null && pnl > 0) realized += Number(pnl)
  }
  const setAside = realized > 0 ? Math.min(realized, Number(target)) : 0
  return { realizedProfit: realized, setAside, target: Number(target) }
}

// --- committed-budget windows (#1) ---
function inWindow(opened, today, window) {
  if (!opened) return false
  if (window === 'day') return opened === today
  const od = new Date(`${opened}T00:00:00Z`), td = new Date(`${today}T00:00:00Z`)
  if (window === 'month') return opened.slice(0, 7) === today.slice(0, 7)
  if (window === 'week') {
    // ISO week: same Monday-anchored week.
    const monday = (d) => { const x = new Date(d); const day = (x.getUTCDay() + 6) % 7; x.setUTCDate(x.getUTCDate() - day); return x.toISOString().slice(0, 10) }
    return monday(od) === monday(td)
  }
  return false
}

export function committedInWindows(openRealPositions, multiplierBySymbol = {}, nowMs = Date.now()) {
  const today = todayISO(nowMs)
  const out = { day: 0, week: 0, month: 0 }
  for (const p of openRealPositions || []) {
    const mult = Number(multiplierBySymbol[p.symbol]) || 1
    const r = openRisk(Number(p.entry) || 0, p.stop == null ? null : Number(p.stop), Number(p.size) || 0, mult)
    if (r == null) continue
    const opened = asDate(p.opened_at)
    for (const win of ['day', 'week', 'month']) if (inWindow(opened, today, win)) out[win] += r
  }
  return out
}

// --- 2/3 profit-giveback exit guide (#6) ---
export function maxFavorableExcursion(side, entry, size, multiplier, highs, lows) {
  let move = 0
  if (side === 'long') {
    const best = (highs || []).length ? Math.max(...highs) : null
    move = best != null ? best - entry : 0
  } else {
    const best = (lows || []).length ? Math.min(...lows) : null
    move = best != null ? entry - best : 0
  }
  return Math.max(move * Number(size) * Number(multiplier), 0)
}

export function twoThirdsTrigger(peakPnl, currentPnl, scale = TWO_THIRDS) {
  if (peakPnl == null || peakPnl <= 0 || currentPnl == null) return false
  return currentPnl <= scale * peakPnl
}

// Compute the exit guide from price bars since entry (ts/high/low) + current price.
export function exitGuideFromBars(p, bars, current, multiplier, scale = TWO_THIRDS) {
  const entry = Number(p.entry), size = Number(p.size)
  const openedMs = p.opened_at ? new Date(p.opened_at).getTime() : 0
  const since = (bars || []).filter((b) => new Date(b.ts).getTime() >= openedMs)
  const highs = since.map((b) => Number(b.high)).filter((x) => !Number.isNaN(x))
  const lows = since.map((b) => Number(b.low)).filter((x) => !Number.isNaN(x))
  const peak = maxFavorableExcursion(p.side, entry, size, multiplier, highs, lows)
  const cur = unrealizedPnl(current, entry, size, p.side, multiplier)
  const triggered = twoThirdsTrigger(peak, cur, scale)
  return { peakPnl: peak, thresholdPnl: peak > 0 ? scale * peak : null, currentPnl: cur, triggered }
}

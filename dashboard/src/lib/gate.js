// Client-side mirror of worker/app/gate.py — the pre-trade checklist logic.
// READ-ONLY: validates the numbers against YOUR rules and warns; it never blocks
// and never places an order. Mirrors the Python so the tests there are the
// source of truth. Returns warnings [{code, severity, message}] + metrics.
import { openRisk, pctOfAccount, rMultiple } from './risk'

export const GATE_CAVEAT = 'Il gate valida disciplina e rischio, NON la direzione.'

export function imminentEvent(events, { symbol, nowMs, withinHours }) {
  const horizon = nowMs + withinHours * 3600_000
  let best = null
  for (const e of events || []) {
    if ((e.importance || '').toLowerCase() !== 'high') continue
    const syms = e.symbols || []
    if (syms.length && !syms.includes(symbol)) continue
    const when = new Date(e.event_time).getTime()
    if (Number.isNaN(when) || when < nowMs || when > horizon) continue
    if (best == null || when < best.when) best = { when, ev: e }
  }
  return best?.ev || null
}

export function evaluateGate({
  symbol, side, entry, stop, target, size, multiplier = 1,
  accountSize, maxRiskPerTradePct, maxPortfolioHeatPct, maxConcurrentPositions,
  rrMin = 1.5, existingHeatPct = 0, openCount = 0,
  thesis, alignment, leanDirection, events = [], nowMs = Date.now(), eventWarnHours = 48,
}) {
  const riskAmount = openRisk(entry, stop, size, multiplier)
  const riskPct = pctOfAccount(riskAmount, accountSize)
  const rr = rMultiple(entry, stop, target)
  const resultingHeatPct = (existingHeatPct || 0) + (riskPct || 0)
  const nConcurrent = openCount + 1

  const w = []
  if (riskPct != null && riskPct > maxRiskPerTradePct)
    w.push({ code: 'risk_per_trade', severity: 'warn', message: `Rischio per trade ${riskPct.toFixed(2)}% oltre il limite ${maxRiskPerTradePct.toFixed(2)}%.` })
  if (resultingHeatPct > maxPortfolioHeatPct)
    w.push({ code: 'heat', severity: 'warn', message: `Heat risultante ${resultingHeatPct.toFixed(2)}% oltre il limite ${maxPortfolioHeatPct.toFixed(2)}%.` })
  if (nConcurrent > maxConcurrentPositions)
    w.push({ code: 'concurrent', severity: 'warn', message: `${nConcurrent} posizioni concorrenti oltre il limite ${maxConcurrentPositions}.` })
  if (rr != null && rr < rrMin)
    w.push({ code: 'rr_low', severity: 'warn', message: `R/R ${rr.toFixed(2)} sotto la soglia ${rrMin.toFixed(2)}.` })
  else if (rr == null)
    w.push({ code: 'rr_missing', severity: 'info', message: 'R/R non calcolabile (manca stop o target).' })

  const ev = events.length ? imminentEvent(events, { symbol, nowMs, withinHours: eventWarnHours }) : null
  if (ev)
    w.push({ code: 'event_risk', severity: 'warn', message: `Rischio evento: «${ev.title}» (${String(ev.event_time).slice(0, 16)}) entro ${eventWarnHours}h — valuta size ridotta o attesa.` })

  if (alignment === 'contrarian')
    w.push({ code: 'contrarian', severity: 'info', message: `Trade CONTRO la lettura macro${leanDirection ? ` (${leanDirection})` : ''}: non è un divieto, ma sii consapevole di andare contro la marea.` })

  return {
    metrics: { riskAmount, riskPct, rr, resultingHeatPct, existingHeatPct, nConcurrent, multiplier, leanDirection, alignment },
    warnings: w,
    caveat: GATE_CAVEAT,
  }
}

// Client-side mirror of worker/app/gate.py — the pre-trade discipline gate.
// READ-ONLY: validates the numbers against YOUR rules and warns; only mandatory
// stop and block-mode budget caps are blocking, and even then it just refuses to
// REGISTER — it never places an order. Mirrors the Python so the tests there are
// the source of truth. Returns warnings [{code, severity, message}] + metrics.
import { openRisk, pctOfAccount, rMultiple } from './risk'

export const GATE_CAVEAT = 'Il gate valida disciplina e rischio, NON la direzione.'

// The user's own rules, quoted verbatim (their words are the strongest nudge).
export const RULE_COUNTERTREND_SHORT =
  'Stai puntando contro il trend (SHORT con prezzo sopra le medie chiave). Regola tua: non puntare al ribasso solo perché «il prezzo è alto». Così hai perso 2500€ sull’oro.'
export const RULE_COUNTERTREND_LONG =
  'Stai comprando in un chiaro downtrend (LONG con prezzo sotto le medie chiave). Regola tua: non entrare solo perché «il prezzo è basso rispetto a cosa?».'
export const RULE_REENTRY =
  'Stai rientrando nella stessa direzione che ha appena perso — è il pattern dell’oro (6 volte di fila).'
export const RULE_ADDING = 'Stai aumentando su un perdente: una posizione aperta nello stesso verso è già in perdita.'
export const RULE_THESIS =
  'Serve una tesi (regola 2.1): una ragione valida e una direzione attesa nel periodo — non «è alto/basso rispetto a cosa?».'

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

// Countertrend INTERCEPTOR — a warning, never the rule itself.
export function trendConflict(side, technicals) {
  if (!technicals) return null
  const mas = {}
  for (const m of technicals.ma || []) mas[m.period] = m
  const above200 = mas[200]?.above
  const above50 = mas[50]?.above
  if (above200 == null && above50 == null) return null
  const uptrend = above200 === true && above50 !== false
  const downtrend = above200 === false && above50 !== true
  if (side === 'short' && uptrend) return RULE_COUNTERTREND_SHORT
  if (side === 'long' && downtrend) return RULE_COUNTERTREND_LONG
  return null
}

function hasLosingSameDir(side, trades) {
  return (trades || []).some((t) => t.side === side && (Number(t.pnl) || 0) < 0)
}

// Kill-switch helpers — closedTrades NEWEST-first.
export function consecutiveLosses(closedTrades) {
  let run = 0
  for (const t of closedTrades || []) {
    const pnl = t.pnl != null ? Number(t.pnl) : Number(t.realized_pnl)
    if (pnl != null && !Number.isNaN(pnl) && pnl < 0) run++
    else break
  }
  return run
}

export function cooldownHit(recentStops, symbol, side, nowMs, cooldownHours) {
  if (!(cooldownHours > 0)) return null
  for (const t of recentStops || []) {
    if (t.symbol !== symbol || t.side !== side) continue
    const when = new Date(t.closed_at).getTime()
    if (Number.isNaN(when)) continue
    const hours = (nowMs - when) / 3_600_000
    if (hours >= 0 && hours <= cooldownHours) return { hoursAgo: hours, cooldownHours }
  }
  return null
}

function budgetStatus(caps, used, riskAmount) {
  if (!caps || riskAmount == null) return []
  const u = used || {}
  const out = []
  for (const [win, label] of [['day', 'giornata'], ['week', 'settimana'], ['month', 'mese']]) {
    const cap = caps[win]
    if (!cap || cap.max == null) continue
    const mx = Number(cap.max)
    const used_ = Number(u[win] || 0)
    const resulting = used_ + riskAmount
    out.push({ window: win, label, max: mx, used: used_, resulting, over: resulting > mx, mode: cap.mode || 'warn' })
  }
  return out
}

export function evaluateGate({
  symbol, side, entry, stop, target, size, multiplier = 1,
  accountSize, maxRiskPerTradePct, maxPortfolioHeatPct, maxConcurrentPositions,
  rrMin = 1.5, existingHeatPct = 0, openCount = 0,
  thesis, alignment, leanDirection, events = [], nowMs = Date.now(), eventWarnHours = 48,
  // discipline guards (opt-in)
  requireThesis = false, atr = null, stopAtrMinMultiple = 1.5, technicals = null,
  recentClosedSameSymbol = [], openSameSymbol = [], budgetCaps = null, budgetUsed = null,
  killswitch = null, consecutiveLossCount = 0, cooldown = null,
}) {
  const riskAmount = openRisk(entry, stop, size, multiplier)
  const riskPct = pctOfAccount(riskAmount, accountSize)
  const rr = rMultiple(entry, stop, target)
  const resultingHeatPct = (existingHeatPct || 0) + (riskPct || 0)
  const nConcurrent = openCount + 1
  const stopDistance = stop == null ? null : Math.abs(entry - stop)

  const w = []

  // STOP mandatory (blocks sizing/registration).
  if (stop == null)
    w.push({ code: 'stop_missing', severity: 'block', message: 'Stop loss obbligatorio: senza stop non si dimensiona né si registra il trade.' })

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

  // Sizing with room — stop must clear normal volatility (k×ATR).
  if (stopDistance != null && atr && atr > 0 && stopAtrMinMultiple > 0) {
    const floor = stopAtrMinMultiple * atr
    if (stopDistance < floor)
      w.push({ code: 'stop_too_tight', severity: 'warn', message: `Stop a ${stopDistance.toFixed(2)} < ${stopAtrMinMultiple}×ATR (${floor.toFixed(2)}): dentro il rumore normale — rischi la chiusura prematura prima che il trade possa svilupparsi. Dai più margine o riduci la size.` })
  }

  // Recurring-error guards (advisory; each cites the user's rule).
  const tc = trendConflict(side, technicals)
  if (tc) w.push({ code: 'countertrend', severity: 'warn', message: tc })
  if (hasLosingSameDir(side, recentClosedSameSymbol)) w.push({ code: 'reentry_losing', severity: 'warn', message: RULE_REENTRY })
  if (hasLosingSameDir(side, openSameSymbol)) w.push({ code: 'adding_to_loser', severity: 'warn', message: RULE_ADDING })
  if (requireThesis && !(thesis || '').trim()) w.push({ code: 'thesis_missing', severity: 'warn', message: RULE_THESIS })

  // Budget caps.
  const budget = budgetStatus(budgetCaps, budgetUsed, riskAmount)
  for (const b of budget) {
    if (b.over)
      w.push({ code: `budget_${b.window}`, severity: b.mode === 'block' ? 'block' : 'warn', message: `Supereresti il budget di ${b.label}: ${b.resulting.toFixed(0)} impegnato / ${b.max.toFixed(0)} max (${b.used.toFixed(0)} già + ${(riskAmount || 0).toFixed(0)} nuovo).` })
  }

  // Kill-switch — soft blocks the user set when lucid (forceable, recorded).
  const ks = killswitch || {}
  if (ks.enabled) {
    const maxL = Number(ks.maxConsecutiveLosses || 0)
    if (maxL > 0 && consecutiveLossCount >= maxL) {
      w.push({ code: 'kill_switch_losses', severity: 'block', message: `${consecutiveLossCount} perdite di fila: le tue regole dicono STOP${ks.until ? ` fino a ${ks.until}` : ''}. Kill-switch che TU hai impostato quando eri lucido — forzalo solo consapevolmente.` })
    }
    if (cooldown && cooldown.hoursAgo != null) {
      w.push({ code: 'cooldown', severity: 'block', message: `Stop preso su ${symbol} ${side} ${cooldown.hoursAgo.toFixed(0)}h fa: cooldown ${cooldown.cooldownHours}h (anti-revenge). Aspetta prima di rientrare nello stesso verso.` })
    }
  }

  const hasBlocking = w.some((x) => x.severity === 'block')
  return {
    metrics: {
      riskAmount, riskPct, rr, resultingHeatPct, existingHeatPct, nConcurrent, multiplier,
      leanDirection, alignment, stopDistance, atr,
      suggestedStopDistance: atr ? stopAtrMinMultiple * atr : null, budget,
    },
    warnings: w,
    hasBlockingWarnings: hasBlocking,
    caveat: GATE_CAVEAT,
  }
}

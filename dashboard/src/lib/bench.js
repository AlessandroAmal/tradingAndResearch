// Client mirror of worker/app/decision/bench.py — the arithmetic of ONE bet.
// READ-ONLY: R:R + cost-adjusted break-even + scenarios + a BS option illustration.
// The ONLY probabilities are the option-IMPLIED ones (passed in). Never a call to act.
import { normCdf } from './options'

function normPdf(x) { return Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI) }
const sign = (dir) => (dir === 'long' ? 1 : -1)

export function costAmount(entry, size, mult, spreadBps, commission = 0) {
  const notional = Math.abs(entry) * size * mult
  return notional * (spreadBps / 10_000) + commission
}

export function rMultiple(entry, stop, target) {
  if (stop == null || target == null) return null
  const risk = Math.abs(entry - stop)
  return risk === 0 ? null : Math.abs(target - entry) / risk
}

export function breakevenWinrate(riskAmt, rewardAmt, cost = 0) {
  const denom = riskAmt + rewardAmt
  return denom <= 0 ? null : (riskAmt + cost) / denom
}

export function betMath({ entry, stop, target, size, multiplier, spreadBps, commission = 0 }) {
  const riskAmt = stop == null ? null : Math.abs(entry - stop) * size * multiplier
  const rewardAmt = target == null ? null : Math.abs(target - entry) * size * multiplier
  const cost = costAmount(entry, size, multiplier, spreadBps, commission)
  const both = riskAmt != null && rewardAmt != null
  return {
    riskAmount: riskAmt, rewardAmount: rewardAmt, costAmount: cost,
    rr: rMultiple(entry, stop, target),
    breakevenWinrate: both ? breakevenWinrate(riskAmt, rewardAmt, cost) : null,
    breakevenWinrateNoCost: both ? breakevenWinrate(riskAmt, rewardAmt, 0) : null,
  }
}

export function pnlAt(price, entry, dir, size, mult) {
  return (price - entry) * size * mult * sign(dir)
}

export function scenarioLadder({ entry, stop, target, atr, direction, size, multiplier }) {
  const rows = []
  const sgn = sign(direction)
  if (atr && atr > 0) {
    for (const k of [2, 1, 0.5]) {
      for (const s of [sgn, -sgn]) {
        const price = entry + s * k * atr
        rows.push({ label: `${s * sgn > 0 ? '+' : '−'}${k} ATR`, price, pnl: pnlAt(price, entry, direction, size, multiplier) })
      }
    }
  }
  if (stop != null) {
    rows.push({ label: 'stop', price: stop, kind: 'stop', pnl: pnlAt(stop, entry, direction, size, multiplier) })
    if (atr && atr > 0) {
      const gap = stop - sgn * atr
      rows.push({ label: 'gap oltre lo stop (−1 ATR)', price: gap, kind: 'gap', pnl: pnlAt(gap, entry, direction, size, multiplier) })
    }
  }
  if (target != null) rows.push({ label: 'target', price: target, kind: 'target', pnl: pnlAt(target, entry, direction, size, multiplier) })
  return rows
}

export function bsPrice(kind, S, K, T, r, sigma) {
  if (!(S > 0 && K > 0 && T > 0 && sigma > 0)) return null
  const d1 = (Math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * Math.sqrt(T))
  const d2 = d1 - sigma * Math.sqrt(T)
  const disc = Math.exp(-r * T)
  return kind === 'call'
    ? S * normCdf(d1) - K * disc * normCdf(d2)
    : K * disc * normCdf(-d2) - S * normCdf(-d1)
}

export function bsThetaDaily(kind, S, K, T, r, sigma) {
  if (!(S > 0 && K > 0 && T > 0 && sigma > 0)) return null
  const d1 = (Math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * Math.sqrt(T))
  const d2 = d1 - sigma * Math.sqrt(T)
  const term = -(S * normPdf(d1) * sigma) / (2 * Math.sqrt(T))
  const disc = Math.exp(-r * T)
  const thetaYear = kind === 'call' ? term - r * K * disc * normCdf(d2) : term + r * K * disc * normCdf(-d2)
  return thetaYear / 365
}

export function optionIllustration({ spot, strike, direction, T, r, sigma, target, contractSize = 1 }) {
  const kind = direction === 'long' ? 'call' : 'put'
  const prem = bsPrice(kind, spot, strike, T, r, sigma)
  if (prem == null) return null
  const breakeven = kind === 'call' ? strike + prem : strike - prem
  let pop = null
  if (breakeven > 0) {
    const d2 = (Math.log(spot / breakeven) + (r - 0.5 * sigma * sigma) * T) / (sigma * Math.sqrt(T))
    pop = kind === 'call' ? normCdf(d2) : 1 - normCdf(d2)
  }
  let rr = null
  if (target != null && prem > 0) {
    const gain = kind === 'call' ? Math.max(target - breakeven, 0) : Math.max(breakeven - target, 0)
    rr = gain / prem
  }
  return {
    kind, strike, premium: prem, breakeven, maxLoss: prem * contractSize, pop, rrToTarget: rr,
    thetaDaily: bsThetaDaily(kind, spot, strike, T, r, sigma),
    note: 'Illustrazione a rischio definito (BS con IV implicita, prob a scadenza). Il desk Options ha le catene reali.',
  }
}

export function verdict(breakevenWr, impliedHit) {
  if (breakevenWr == null || impliedHit == null) {
    return { edge: null, text: 'Dati insufficienti per il confronto (servono stop, target e odds impliciti).' }
  }
  const edge = impliedHit - breakevenWr
  return {
    breakevenWinrate: breakevenWr, impliedHit, edge,
    text: `Per andare in pari ti serve ragione il ${(breakevenWr * 100).toFixed(0)}% delle volte (costi inclusi). `
      + `Il mercato prezza ~${(impliedHit * 100).toFixed(0)}% che il prezzo tocchi il tuo target (approssimazione a scadenza, non first-touch). `
      + (edge > 0
        ? 'Gli odds impliciti sono già SOPRA il tuo pareggio: il margine dipende comunque dalla tua tesi e dai costi.'
        : 'Gli odds impliciti sono SOTTO il tuo pareggio: senza una tesi per cui il mercato sbaglia, il valore atteso è ~zero prima dei costi, negativo dopo.'),
    disclaimer: 'Nessun EV previsto: solo odds impliciti + aritmetica del payoff. La decisione è tua.',
  }
}

// Implied prob of TOUCHING target / STOP at the horizon, using the nearest expiry's
// IV (terminal approximation, not first-touch — declared). Returns {probTarget,
// probStop, expiryDays, atmIv, note} or nulls.
export function impliedOnLevels({ implied, target, stop, horizonDays, direction }) {
  const hz = (implied?.horizons || []).filter((h) => h.available && h.atm_iv)
  const spot = implied?.spot
  const r = implied?.risk_free_rate ?? 0.04
  if (!hz.length || !spot) return { probTarget: null, probStop: null }
  const pick = hz.reduce((a, b) => (Math.abs((b.days_to_expiry || 0) - horizonDays) < Math.abs((a.days_to_expiry || 0) - horizonDays) ? b : a))
  const T = Math.max(horizonDays, 0.5) / 365
  const iv = pick.atm_iv
  const d2 = (K) => (Math.log(spot / K) + (r - 0.5 * iv * iv) * T) / (iv * Math.sqrt(T))
  const pAbove = (K) => normCdf(d2(K))
  let probTarget = null; let probStop = null
  if (target != null) probTarget = direction === 'long' ? pAbove(target) : 1 - pAbove(target)
  if (stop != null) probStop = direction === 'long' ? 1 - pAbove(stop) : pAbove(stop)
  return { probTarget, probStop, expiryDays: pick.days_to_expiry, expiry: pick.expiry, atmIv: iv, spot, T,
    note: `IV dalla scadenza ${pick.expiry || ''} (${pick.days_to_expiry}g) usata per il tuo orizzonte ${horizonDays}g; prob a scadenza, non first-touch.` }
}

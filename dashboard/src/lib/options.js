// Client-side mirror of worker/app/options.py (structures + payoff + implied
// probability). IV/Greeks come from the worker (stored in options_chains);
// the dashboard only redraws payoff and recomputes POP from stored IV.
// READ-ONLY: analysis, never an order. POP is the risk-neutral (implied)
// probability — not a forecast.

function erf(x) {
  // Abramowitz-Stegun 7.1.26
  const t = 1 / (1 + 0.3275911 * Math.abs(x))
  const y =
    1 -
    (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) *
      t *
      Math.exp(-x * x)
  return x >= 0 ? y : -y
}
export function normCdf(x) {
  return 0.5 * (1 + erf(x / Math.SQRT2))
}

export function probAbove(S, X, T, r, sigma) {
  if (!(T > 0) || !(sigma > 0) || !(S > 0) || !(X > 0)) return null
  const d2 = (Math.log(S / X) + (r - 0.5 * sigma * sigma) * T) / (sigma * Math.sqrt(T))
  return normCdf(d2)
}
export function probBelow(S, X, T, r, sigma) {
  const p = probAbove(S, X, T, r, sigma)
  return p == null ? null : 1 - p
}

// legs: [{kind:'call'|'put'|'stock', side:'long'|'short', strike, premium, qty}]
export function legPnl(leg, S) {
  const sgn = leg.side === 'long' ? 1 : -1
  let intrinsic
  if (leg.kind === 'stock') intrinsic = S - leg.premium
  else if (leg.kind === 'call') intrinsic = Math.max(S - leg.strike, 0) - leg.premium
  else intrinsic = Math.max(leg.strike - S, 0) - leg.premium
  return sgn * (leg.qty ?? 1) * intrinsic
}
export function structurePnl(legs, S) {
  return legs.reduce((s, leg) => s + legPnl(leg, S), 0)
}
export function payoffCurve(legs, lo, hi, steps = 80) {
  if (steps < 2 || hi <= lo) return []
  const step = (hi - lo) / (steps - 1)
  return Array.from({ length: steps }, (_, i) => {
    const price = lo + i * step
    return { price, pnl: structurePnl(legs, price) }
  })
}

// Single leg metrics (premium per share).
export function singleLeg(optionType, side, strike, premium) {
  let maxLoss, maxGain, breakeven, profitSide
  if (optionType === 'call') {
    breakeven = strike + premium
    if (side === 'long') { maxLoss = premium; maxGain = null; profitSide = 'above' }
    else { maxLoss = null; maxGain = premium; profitSide = 'below' }
  } else {
    breakeven = strike - premium
    if (side === 'long') { maxLoss = premium; maxGain = Math.max(strike - premium, 0); profitSide = 'below' }
    else { maxLoss = Math.max(strike - premium, 0); maxGain = premium; profitSide = 'above' }
  }
  const legs = [{ kind: optionType, side, strike, premium, qty: 1 }]
  return { legs, netCost: side === 'long' ? premium : -premium, maxLoss, maxGain, breakeven, profitSide }
}

// Vertical spread (two same-type legs).
export function verticalSpread(optionType, longStrike, longPrem, shortStrike, shortPrem) {
  const width = Math.abs(shortStrike - longStrike)
  const net = longPrem - shortPrem // >0 debit
  let maxLoss, maxGain
  if (net >= 0) { maxLoss = net; maxGain = width - net }
  else { maxGain = -net; maxLoss = width + net }
  let breakeven, profitSide
  if (optionType === 'call') {
    breakeven = Math.min(longStrike, shortStrike) + Math.abs(net)
    profitSide = net >= 0 ? 'above' : 'below'
  } else {
    breakeven = Math.max(longStrike, shortStrike) - Math.abs(net)
    profitSide = net >= 0 ? 'below' : 'above'
  }
  const legs = [
    { kind: optionType, side: 'long', strike: longStrike, premium: longPrem, qty: 1 },
    { kind: optionType, side: 'short', strike: shortStrike, premium: shortPrem, qty: 1 },
  ]
  return { legs, netCost: net, maxLoss: Math.abs(maxLoss), maxGain: Math.abs(maxGain), breakeven, profitSide }
}

export function probabilityOfProfit(metrics, S, T, r, sigma) {
  if (metrics.breakeven == null) return null
  return metrics.profitSide === 'above'
    ? probAbove(S, metrics.breakeven, T, r, sigma)
    : probBelow(S, metrics.breakeven, T, r, sigma)
}

export function yearsTo(expiry, nowMs = Date.now()) {
  const d = new Date(`${expiry.slice(0, 10)}T00:00:00Z`).getTime()
  return Math.max(d - nowMs, 0) / (365 * 86_400_000)
}

// Approximate spot from a chain: the call strike whose |delta-0.5| is smallest.
export function approxSpot(chain) {
  const calls = chain.filter((c) => c.option_type === 'call' && c.delta != null)
  if (!calls.length) return null
  let best = calls[0]
  for (const c of calls) if (Math.abs(c.delta - 0.5) < Math.abs(best.delta - 0.5)) best = c
  return best.strike
}

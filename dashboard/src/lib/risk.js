// Client-side mirror of worker/app/risk.py for the positions table + sizing
// calculator. Read-only: sizing is a calculator, breaches are flags — never
// an order. Returns null on insufficient inputs so the UI degrades.
// *_pct values are percentages (1.0 === 1%).

export function positionSize(accountSize, riskPct, entry, stop, multiplier = 1) {
  if (stop == null || !(accountSize > 0) || !(riskPct > 0) || !(multiplier > 0)) return null
  const perUnit = Math.abs(entry - stop) * multiplier
  if (!(perUnit > 0)) return null
  return (accountSize * (riskPct / 100)) / perUnit
}

export function openRisk(entry, stop, size, multiplier = 1) {
  if (stop == null) return null
  return Math.abs(entry - stop) * size * multiplier
}

export function pctOfAccount(amount, accountSize) {
  if (amount == null || !(accountSize > 0)) return null
  return (amount / accountSize) * 100
}

export function rMultiple(entry, stop, target) {
  if (stop == null || target == null) return null
  const risk = Math.abs(entry - stop)
  if (risk === 0) return null
  return Math.abs(target - entry) / risk
}

export function unrealizedPnl(current, entry, size, side, multiplier = 1) {
  if (current == null) return null
  const sign = side === 'long' ? 1 : -1
  return (current - entry) * size * sign * multiplier
}

export function stopBreached(current, stop, side) {
  if (current == null || stop == null) return false
  return side === 'long' ? current <= stop : current >= stop
}

export function daysUntil(deadlineStr, nowMs = Date.now()) {
  if (!deadlineStr) return null
  const d = new Date(`${deadlineStr.slice(0, 10)}T00:00:00Z`).getTime()
  if (Number.isNaN(d)) return null
  return Math.ceil((d - nowMs) / 86_400_000)
}

// Full per-position evaluation used by the positions table.
export function evaluatePosition(p, { current, multiplier, accountSize, maxRiskPerTradePct, warnDays, nowMs }) {
  const entry = Number(p.entry)
  const stop = p.stop != null ? Number(p.stop) : null
  const target = p.target != null ? Number(p.target) : null
  const size = Number(p.size)
  const oRisk = openRisk(entry, stop, size, multiplier)
  const oRiskPct = pctOfAccount(oRisk, accountSize)
  const dtd = daysUntil(p.deadline, nowMs)
  return {
    openRisk: oRisk,
    openRiskPct: oRiskPct,
    rMultiple: rMultiple(entry, stop, target),
    pnl: unrealizedPnl(current, entry, size, p.side, multiplier),
    daysToDeadline: dtd,
    stopBreached: stopBreached(current, stop, p.side),
    riskPerTradeBreached: oRiskPct != null && oRiskPct > maxRiskPerTradePct,
    deadlineNear: dtd != null && dtd <= warnDays,
  }
}

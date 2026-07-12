// Client mirror of worker/app/experiment/aggregate.py — aggregate CLOSED paper
// experiment positions into evidence. READ-ONLY: n always shown, below threshold
// is NOT a probability, none of this is a signal.

export function flatten(p) {
  const c = p.entry_conditions || {}
  const sur = c.surprise || {}
  let ret = c.return_pct
  if (ret == null && p.realized_pnl != null && p.entry) ret = Number(p.realized_pnl) / Number(p.entry)
  return {
    event: c.event, symbol: p.symbol, delay_min: c.delay_min, horizon: c.horizon,
    direction: c.direction, surprise_dir: sur.direction, return_pct: ret,
  }
}

export function aggregate(positions, groupKeys, { minSample = 20 } = {}) {
  const rows = (positions || []).filter((p) => p.status === 'closed').map(flatten)
    .filter((r) => r.return_pct != null)
  const groups = new Map()
  for (const r of rows) {
    const gk = groupKeys.map((k) => r[k]).join('|')
    if (!groups.has(gk)) groups.set(gk, { key: groupKeys.map((k) => r[k]), rets: [] })
    groups.get(gk).rets.push(Number(r.return_pct))
  }
  const out = []
  for (const { key, rets } of groups.values()) {
    const n = rets.length
    const sorted = [...rets].sort((a, b) => a - b)
    const median = n % 2 ? sorted[(n - 1) / 2] : (sorted[n / 2 - 1] + sorted[n / 2]) / 2
    const mean = rets.reduce((a, b) => a + b, 0) / n
    const variance = rets.reduce((a, b) => a + (b - mean) ** 2, 0) / n
    out.push({
      group: Object.fromEntries(groupKeys.map((k, i) => [k, key[i]])),
      n, pctPositive: rets.filter((x) => x > 0).length / n, meanReturn: mean,
      medianReturn: median, stdev: n > 1 ? Math.sqrt(variance) : null, sufficient: n >= minSample,
    })
  }
  out.sort((a, b) => b.n - a.n)
  return out
}

export const DELAY_LABEL = { 5: 't+5min', 30: 't+30min', 120: 't+2h', 1440: 't+1g' }
export const SURPRISE_LABEL = { positive: 'sorpresa +', negative: 'sorpresa −', inline: 'in linea' }

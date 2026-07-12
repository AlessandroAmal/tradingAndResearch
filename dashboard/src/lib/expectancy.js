// Client mirror of worker/app/expectancy.py — long-run math of the user's OWN
// trades. MEASURED, never predicted; n + intervals always; paper/real separable.
// Seeded PRNG (mulberry32) so bootstrap/Monte-Carlo are stable across renders.

export const MIN_SAMPLE = 20

function mulberry32(seed) {
  let a = seed >>> 0
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function tradeR(entry, stop, realizedPnl, size, mult) {
  if (stop == null || realizedPnl == null) return null
  const risk = Math.abs(Number(entry) - Number(stop)) * Number(size) * Number(mult)
  return risk > 0 ? Number(realizedPnl) / risk : null
}

// Build measured trades from CLOSED positions (experiment excluded by caller).
export function tradesFromPositions(positions, multiplierBySymbol = {}) {
  return (positions || [])
    .filter((p) => p.status === 'closed' && p.realized_pnl != null && !p.experiment)
    .map((p) => {
      const mult = Number(multiplierBySymbol[p.symbol]) || 1
      const c = p.entry_conditions || {}
      const warnings = c.warnings || []
      return {
        symbol: p.symbol, paper: !!p.paper, pnl: Number(p.realized_pnl),
        r: tradeR(p.entry, p.stop, p.realized_pnl, p.size, mult),
        riskFrac: null, entry: Number(p.entry), stop: p.stop, size: Number(p.size), mult,
        forced: Array.isArray(warnings) && warnings.length > 0,
        tag: c.tag || c.setup_tag || null, closed_at: p.closed_at,
      }
    })
}

export function wilsonCi(wins, n, z = 1.96) {
  if (n <= 0) return null
  const p = wins / n, z2 = z * z, denom = 1 + z2 / n
  const centre = (p + z2 / (2 * n)) / denom
  const half = (z * Math.sqrt((p * (1 - p)) / n + z2 / (4 * n * n))) / denom
  return [Math.max(0, centre - half), Math.min(1, centre + half)]
}

export function bootstrapCi(values, { nBoot = 2000, alpha = 0.05, seed = 12345 } = {}) {
  const vals = values.filter((v) => v != null).map(Number)
  const n = vals.length
  if (n < 2) return null
  const rnd = mulberry32(seed)
  const means = []
  for (let b = 0; b < nBoot; b++) {
    let s = 0
    for (let i = 0; i < n; i++) s += vals[Math.floor(rnd() * n)]
    means.push(s / n)
  }
  means.sort((a, b) => a - b)
  return [means[Math.floor((alpha / 2) * nBoot)], means[Math.min(nBoot - 1, Math.floor((1 - alpha / 2) * nBoot))]]
}

export function expectancyStats(trades, { minSample = MIN_SAMPLE } = {}) {
  const pnls = trades.filter((t) => t.pnl != null).map((t) => Number(t.pnl))
  const rs = trades.filter((t) => t.r != null).map((t) => Number(t.r))
  const n = pnls.length
  if (n === 0) return { n: 0, sufficient: false, minSample, note: 'Nessun trade chiuso: niente da misurare.' }
  const wins = pnls.filter((p) => p > 0), losses = pnls.filter((p) => p < 0)
  const winR = rs.filter((r) => r > 0), lossR = rs.filter((r) => r < 0).map((r) => -r)
  let maxStreak = 0, streak = 0
  for (const p of pnls) { streak = p < 0 ? streak + 1 : 0; maxStreak = Math.max(maxStreak, streak) }
  const mean = (a) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : null)
  return {
    n, nWithR: rs.length, sufficient: n >= minSample, minSample,
    winRate: wins.length / n, winRateCi: wilsonCi(wins.length, n),
    avgWinR: mean(winR), avgLossR: mean(lossR),
    expectancyR: mean(rs), expectancyRCi: rs.length >= 2 ? bootstrapCi(rs) : null,
    expectancyEur: mean(pnls), expectancyEurCi: n >= 2 ? bootstrapCi(pnls) : null,
    profitFactor: losses.length ? wins.reduce((a, b) => a + b, 0) / Math.abs(losses.reduce((a, b) => a + b, 0)) : null,
    maxConsecutiveLosses: maxStreak,
    note: n >= minSample ? null : `Campione insufficiente (n=${n} < ${minSample}): questi numeri sono RUMORE, continua a raccogliere.`,
  }
}

export function riskOfRuin({ winRate, rr, riskFrac, drawdown = 0.5, targetMultiple = 2, nRuns = 8000, maxTrades = 4000, seed = 7 }) {
  if (!(winRate > 0 && winRate < 1) || rr <= 0 || !(riskFrac > 0 && riskFrac < 1)) return null
  const rnd = mulberry32(seed)
  const ruinLevel = 1 - drawdown
  let ruined = 0
  for (let run = 0; run < nRuns; run++) {
    let cap = 1
    for (let t = 0; t < maxTrades; t++) {
      cap *= rnd() < winRate ? 1 + riskFrac * rr : 1 - riskFrac
      if (cap <= ruinLevel) { ruined++; break }
      if (cap >= targetMultiple) break
    }
  }
  return ruined / nRuns
}

export function ruinCurve({ winRate, rr, currentFrac, fracs = [0.005, 0.01, 0.015, 0.02, 0.03, 0.05], ...kw }) {
  return fracs.map((fr) => ({ riskFrac: fr, ruin: riskOfRuin({ winRate, rr, riskFrac: fr, ...kw }), current: Math.abs(fr - currentFrac) < 1e-9 }))
}

export function kellyFraction(winRate, rr) { return rr <= 0 ? 0 : winRate - (1 - winRate) / rr }

export function kellyAdjusted(stats) {
  const n = stats.n || 0
  const { winRate: wr, avgWinR: aw, avgLossR: al, winRateCi: ci } = stats
  if (!wr || !aw || !al || al <= 0 || !ci) {
    return { proven: false, n, note: `Edge non misurabile ancora (n=${n}). Size suggerita: minima / di apprendimento.` }
  }
  const rr = aw / al
  const kellyMean = kellyFraction(wr, rr)
  const kellyLb = kellyFraction(ci[0], rr)
  const proven = kellyLb > 0 && n >= (stats.minSample || MIN_SAMPLE)
  return {
    proven, n, rr, kellyMean, kellyLower: kellyLb,
    halfKelly: Math.max(kellyLb, 0) / 2, quarterKelly: Math.max(kellyLb, 0) / 4,
    note: proven
      ? 'Quanto puoi permetterti dato ciò che è DIMOSTRATO, non ciò che speri.'
      : `Il tuo edge non è ancora dimostrato dai dati (n=${n}). Size suggerita: minima / di apprendimento.`,
  }
}

export function processScorecard(trades, { minSample = MIN_SAMPLE } = {}) {
  const clean = trades.filter((t) => !t.forced), forced = trades.filter((t) => t.forced)
  const total = trades.length
  return {
    n: total,
    pctClean: total ? clean.length / total : null,
    pctForced: total ? forced.length / total : null,
    clean: expectancyStats(clean, { minSample }), forced: expectancyStats(forced, { minSample }),
    note: 'La disciplina è misurabile: expectancy dei trade dentro le regole vs forzati (con n di entrambi).',
  }
}

// Average risk-per-trade fraction actually used, from the trades (fallback: cap).
export function avgRiskFrac(trades, accountSize, fallbackPct) {
  const fr = trades.map((t) => (t.stop != null && accountSize > 0
    ? (Math.abs(t.entry - Number(t.stop)) * t.size * t.mult) / accountSize : null)).filter((x) => x != null)
  if (fr.length) return fr.reduce((a, b) => a + b, 0) / fr.length
  return fallbackPct != null ? fallbackPct / 100 : null
}

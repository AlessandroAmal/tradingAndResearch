// Client mirror of worker/app/concentration.py — thematic concentration.
// Positions on different tickers can be the SAME bet (e.g. AI/data-center capex):
// in a de-rating they fall together, so apparent diversification is not real.
// READ-ONLY: warns, never trades, makes NO directional call.

export const THEME_LABELS = {
  ai_datacenter: 'AI / data-center capex',
  semis: 'Semiconduttori',
  ev: 'Veicoli elettrici',
  pharma: 'Farmaceutico',
  financials: 'Finanziari',
}

// positions: [{symbol, notional}] ; themesBySymbol: {symbol: [themes]}
export function themeConcentration(positions, themesBySymbol, { warnMinPositions = 2, labels } = {}) {
  const lab = { ...THEME_LABELS, ...(labels || {}) }
  const total = (positions || []).reduce((a, p) => a + Math.abs(Number(p.notional) || 0), 0)
  const byTheme = {}
  for (const p of positions || []) {
    const notl = Math.abs(Number(p.notional) || 0)
    for (const th of themesBySymbol[p.symbol] || []) {
      const e = byTheme[th] || (byTheme[th] = { symbols: new Set(), notional: 0 })
      e.symbols.add(p.symbol)
      e.notional += notl
    }
  }
  const out = Object.entries(byTheme).map(([th, e]) => ({
    theme: th,
    label: lab[th] || th,
    symbols: [...e.symbols].sort(),
    positions: e.symbols.size,
    notional: e.notional,
    weight: total > 0 ? e.notional / total : null,
    concentrated: e.symbols.size >= warnMinPositions,
  }))
  out.sort((a, b) => (b.concentrated - a.concentrated) || (b.notional - a.notional))
  return out
}

// Build {symbol: [themes]} from the instruments table (themes column is jsonb).
export function themesBySymbol(instruments) {
  const m = {}
  for (const i of instruments || []) {
    const t = i.themes
    if (Array.isArray(t) && t.length) m[i.symbol] = t
  }
  return m
}

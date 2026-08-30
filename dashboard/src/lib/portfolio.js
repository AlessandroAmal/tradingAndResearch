// Real-portfolio valuation math — PURE and tested (test/portfolio.test.mjs).
//
// Dual currency: each holding is valued in its NATIVE currency and converted to
// EUR via the EUR/<ccy> rate (units of the foreign currency per 1 EUR, e.g.
// EURUSD=X → USD per EUR, so EUR = native_USD / rate). P&L is split into:
//   • price P&L  = the instrument's move, valued at TODAY's fx
//   • fx P&L     = the cost basis revalued by the fx move (buy-date → today)
// so on a USD stock you can see how much of the gain/loss is currency, not price.
//
// HONEST about missing data: a missing price or fx rate yields null ("n/d"),
// never an estimate. For a non-base currency with no buy-date fx rate we can't
// value the cost in EUR, so EUR total P&L and fx P&L are null (native P&L% and
// the current EUR value still show).

const BASE = 'EUR'

function num(v) {
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

// Native value → EUR. Base currency passes through; missing/zero rate → null.
export function toEur(valueNative, currency, rate, base = BASE) {
  if (valueNative == null) return null
  if ((currency || base).toUpperCase() === base) return valueNative
  if (rate == null || rate === 0) return null
  return valueNative / rate
}

// Nearest close at-or-before `date` from an ascending [{ts, close}] series, or the
// earliest available if the date predates the series; null if the series is empty.
export function rateAtDate(series, date) {
  if (!series || !series.length) return null
  if (!date) return num(series[series.length - 1].close)
  const target = String(date).slice(0, 10)
  let picked = null
  for (const row of series) {
    if (String(row.ts).slice(0, 10) <= target) picked = row
    else break
  }
  return num((picked || series[0]).close)
}

// Value one holding. `price` = current native price; `rateNow`/`rateBuy` = EUR/ccy
// now / at the buy date (null when unknown). The average COST is in its own
// currency (`avg_price_currency`, default EUR = the account currency): the user
// reasons in EUR, so by default cost_EUR = quantity × avg_price EXACTLY, no
// conversion. The price/fx split needs the buy-date FX (to value the native
// purchase price); without it the split is n/d but the total EUR P&L still shows.
export function valueHolding(h, price, rateNow, rateBuy, base = BASE) {
  const qty = num(h.quantity)
  const avg = num(h.avg_price)
  const cur = (h.currency || base).toUpperCase()                    // quote currency
  const costCur = (h.avg_price_currency || base).toUpperCase()      // cost currency (default EUR)
  const isBase = cur === base

  const rN = isBase ? 1 : rateNow
  const rB = isBase ? 1 : rateBuy            // may be null → split n/d

  const valueNative = qty != null && price != null ? qty * price : null
  const valueEur = toEur(valueNative, cur, rN, base)

  // Cost in EUR + the equivalent NATIVE purchase price (for the price/fx split).
  let costEur = null, avgNative = null
  if (qty != null && avg != null) {
    if (costCur === base) {
      costEur = qty * avg                                            // exact — paid in EUR
      avgNative = isBase ? avg : (rB != null ? avg * rB : null)      // derive native (needs buy FX)
    } else {
      avgNative = avg                                                // cost already native
      costEur = isBase ? qty * avg : (rB != null ? (qty * avg) / rB : null)
    }
  }

  const pnlAbsEur = valueEur != null && costEur != null ? valueEur - costEur : null
  const pnlPct = pnlAbsEur != null && costEur ? pnlAbsEur / costEur : null   // EUR return %

  let pnlPriceEur = null, pnlFxEur = null
  if (isBase && pnlAbsEur != null) {
    pnlFxEur = 0
    pnlPriceEur = pnlAbsEur
  } else if (!isBase && qty != null && price != null && avgNative != null && rN != null && rB != null) {
    pnlPriceEur = (qty * (price - avgNative)) / rN
    pnlFxEur = qty * avgNative * (1 / rN - 1 / rB)
  }

  return {
    symbol: h.symbol, currency: cur, costCurrency: costCur, quantity: qty, avgPrice: avg, price,
    valueNative, valueEur, costEur, pnlAbsEur, pnlPct, pnlPriceEur, pnlFxEur,
    rateNow: rN, rateBuy: rB,
    fxMissing: !isBase && rN == null,
    fxBuyMissing: !isBase && rB == null,       // split not reconstructable
  }
}

// Value one holding ROW honoring its valuation mode. Manual rows carry their own
// EUR value (negative for a liability, e.g. a mortgage) and never need a price;
// market rows are valued from the live price + fx. Returns a uniform shape.
export function valueRow(h, price, rateNow, rateBuy, base = BASE) {
  const mode = h.valuation_mode || (h.manual_value != null ? 'manual' : 'market')
  if (mode === 'manual') {
    const v = num(h.manual_value)
    return {
      symbol: h.symbol, category: h.category, currency: base, manual: true,
      isLiability: !!h.is_liability, closed: h.status === 'closed',
      quantity: num(h.quantity), avgPrice: num(h.avg_price), price: null,
      valueNative: v, valueEur: v, costEur: v, pnlAbsEur: null, pnlPct: null,
      pnlPriceEur: null, pnlFxEur: null, name: h.name, isin: h.isin, note: h.note,
    }
  }
  return {
    ...valueHolding(h, price, rateNow, rateBuy, base),
    category: h.category, manual: false, isLiability: !!h.is_liability,
    closed: h.status === 'closed', name: h.name, isin: h.isin, note: h.note,
  }
}

// Group valued rows by category with market/manual/liability subtotals. Closed
// rows are excluded from the live value (kept as history). Returns an object
// keyed by category plus a `_main` (patrimony ex sub-portfolios) roll-up.
export function byCategory(valued, { subPortfolioNames = ['Portafogli Figli'] } = {}) {
  const cats = {}
  for (const v of valued) {
    if (v.closed) continue
    const c = v.category || 'Altro'
    cats[c] = cats[c] || { category: c, market: 0, manual: 0, valueEur: 0, nd: 0, rows: [], isSub: subPortfolioNames.includes(c) }
    cats[c].rows.push(v)
    if (v.valueEur == null) { cats[c].nd++; continue }
    if (v.manual) cats[c].manual += v.valueEur; else cats[c].market += v.valueEur
    cats[c].valueEur += v.valueEur
  }
  let mainValue = 0, mainMarket = 0, mainManual = 0, subValue = 0
  for (const c of Object.values(cats)) {
    if (c.isSub) { subValue += c.valueEur } else { mainValue += c.valueEur; mainMarket += c.market; mainManual += c.manual }
  }
  return { cats, main: { valueEur: mainValue, market: mainMarket, manual: mainManual }, sub: { valueEur: subValue } }
}

// Portfolio totals in EUR + per-currency exposure + weights. `valued` = array of
// valueHolding() results. `partial` flags that some EUR values were n/d.
export function portfolioTotals(valued, base = BASE) {
  let valueEur = 0
  let pnlEur = 0
  let anyPnl = false
  let partial = false
  const byCurrency = {}
  for (const v of valued) {
    if (v.valueEur == null) { partial = true; continue }
    valueEur += v.valueEur
    const c = v.currency || base
    byCurrency[c] = (byCurrency[c] || 0) + v.valueEur
    if (v.pnlAbsEur != null) { pnlEur += v.pnlAbsEur; anyPnl = true }
    else partial = true
  }
  const exposure = Object.entries(byCurrency)
    .map(([currency, eur]) => ({ currency, eur, pct: valueEur ? eur / valueEur : null }))
    .sort((a, b) => b.eur - a.eur)
  const withWeights = valued.map((v) => ({
    ...v, weight: v.valueEur != null && valueEur ? v.valueEur / valueEur : null,
  }))
  const costEur = valued.reduce((s, v) => s + (v.costEur ?? 0), 0)
  return {
    valueEur, pnlEur: anyPnl ? pnlEur : null,
    pnlPct: anyPnl && costEur ? pnlEur / costEur : null,
    exposure, partial, holdings: withWeights,
  }
}

// Real-portfolio valuation: currency conversion + P&L price/fx decomposition +
// totals + exposure + honest missing-data handling.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { toEur, rateAtDate, valueHolding, portfolioTotals, valueRow, byCategory } from '../src/lib/portfolio.js'

const approx = (a, b, tol = 1e-6) => assert.ok(Math.abs(a - b) <= tol, `${a} ≈ ${b}`)

test('toEur converts via EUR/ccy rate, base passes through, missing → null', () => {
  approx(toEur(1000, 'USD', 1.1), 909.0909090909, 1e-6)  // USD/EUR=1.1 → 1000/1.1
  approx(toEur(500, 'EUR', null), 500)                    // base: rate ignored
  assert.equal(toEur(1000, 'USD', null), null)            // missing rate → n/d
  assert.equal(toEur(null, 'USD', 1.1), null)
})

test('rateAtDate picks nearest close at-or-before the date', () => {
  const s = [{ ts: '2026-01-01', close: 1.0 }, { ts: '2026-06-01', close: 1.1 },
             { ts: '2026-08-01', close: 1.2 }]
  approx(rateAtDate(s, '2026-07-15'), 1.1)   // between → earlier
  approx(rateAtDate(s, '2026-08-10'), 1.2)   // after last → last
  approx(rateAtDate(s, '2025-01-01'), 1.0)   // before first → earliest
  assert.equal(rateAtDate([], '2026-01-01'), null)
})

test('USD holding, cost in EUR (default): exact cost + split via derived native price', () => {
  // 10 sh, paid €100/sh (EUR cost), now 120 USD; EUR/USD buy 1.0 → now 1.2.
  const v = valueHolding({ symbol: 'MSFT', quantity: 10, avg_price: 100, currency: 'USD', avg_price_currency: 'EUR' },
    120, 1.2, 1.0)
  approx(v.valueNative, 1200)
  approx(v.valueEur, 1000)                    // 1200 / 1.2
  approx(v.costEur, 1000)                     // 10 × €100 — EXACT, no conversion
  approx(v.pnlAbsEur, 0)
  // derived native purchase price = €100 × 1.0 = 100 USD
  approx(v.pnlPriceEur, 166.6666667, 1e-4)    // 10*(120-100)/1.2
  approx(v.pnlFxEur, -166.6666667, 1e-4)      // 10*100*(1/1.2 - 1/1.0)
  approx(v.pnlPriceEur + v.pnlFxEur, v.pnlAbsEur, 1e-6)   // split closes
  approx(v.pnlPct, 0)                          // EUR return %
})

test('cost in native currency (explicit avg_price_currency): converts at buy FX', () => {
  const v = valueHolding({ symbol: 'X', quantity: 10, avg_price: 100, currency: 'USD', avg_price_currency: 'USD' },
    120, 1.2, 1.0)
  approx(v.costEur, 1000)                      // 10*100 USD / 1.0
  approx(v.valueEur, 1000)
  approx(v.pnlPriceEur, 166.6666667, 1e-4)
})

test('EUR holding: no fx, fx P&L is zero', () => {
  const v = valueHolding({ symbol: 'X.MI', quantity: 5, avg_price: 10, currency: 'EUR' },
    12, null, null)
  approx(v.valueEur, 60)
  approx(v.pnlAbsEur, 10)
  approx(v.pnlFxEur, 0)
  approx(v.pnlPriceEur, 10)
})

test('EUR-cost total always computable; missing buy-FX only n/d for the split', () => {
  const noPrice = valueHolding({ symbol: 'A', quantity: 3, avg_price: 5, currency: 'USD', avg_price_currency: 'EUR' },
    null, 1.1, 1.0)
  assert.equal(noPrice.valueEur, null)          // no price → value n/d

  const noBuyFx = valueHolding({ symbol: 'B', quantity: 3, avg_price: 5, currency: 'USD', avg_price_currency: 'EUR' },
    6, 1.1, null)                               // no buy-date rate
  approx(noBuyFx.valueEur, 16.3636364, 1e-4)    // current value computable
  approx(noBuyFx.costEur, 15)                    // 3 × €5 — EXACT (EUR cost)
  approx(noBuyFx.pnlAbsEur, 16.3636364 - 15, 1e-4)  // TOTAL still shown
  assert.equal(noBuyFx.pnlPriceEur, null)       // only the split is n/d…
  assert.equal(noBuyFx.pnlFxEur, null)          // …no buy FX to reconstruct it
  assert.ok(noBuyFx.fxBuyMissing)
})

test('portfolio totals, weights, currency exposure, partial flag', () => {
  const valued = [
    valueHolding({ symbol: 'MSFT', quantity: 10, avg_price: 100, currency: 'USD' }, 120, 1.2, 1.0),
    valueHolding({ symbol: 'X.MI', quantity: 100, avg_price: 10, currency: 'EUR' }, 11, null, null),
  ]
  const t = portfolioTotals(valued)
  approx(t.valueEur, 1000 + 1100)               // 1000 EUR + 1100 EUR
  const usd = t.exposure.find((e) => e.currency === 'USD')
  const eur = t.exposure.find((e) => e.currency === 'EUR')
  approx(usd.eur, 1000); approx(eur.eur, 1100)
  approx(usd.pct + eur.pct, 1, 1e-9)
  const msft = t.holdings.find((h) => h.symbol === 'MSFT')
  approx(msft.weight, 1000 / 2100, 1e-6)
  assert.equal(t.partial, false)
})

test('partial totals when an EUR value is n/d', () => {
  const valued = [
    valueHolding({ symbol: 'EUR1', quantity: 1, avg_price: 1, currency: 'EUR' }, 2, null, null),
    valueHolding({ symbol: 'USD1', quantity: 1, avg_price: 1, currency: 'USD' }, 2, null, 1.0), // no now-fx
  ]
  const t = portfolioTotals(valued)
  assert.equal(t.partial, true)                 // USD1 valueEur is n/d
  approx(t.valueEur, 2)                          // only the EUR holding counts
})

test('valueRow: manual item uses its own EUR value; liability is negative', () => {
  const gold = valueRow({ symbol: 'MANUAL:oro', valuation_mode: 'manual', manual_value: 2550, category: 'Commodity' }, null, null, null)
  assert.equal(gold.manual, true); approx(gold.valueEur, 2550); assert.equal(gold.price, null)
  const mortgage = valueRow({ symbol: 'MANUAL:mutuo', valuation_mode: 'manual', manual_value: -120000, is_liability: true }, null, null, null)
  assert.equal(mortgage.isLiability, true); approx(mortgage.valueEur, -120000)
})

test('valueRow: market item values from price+fx', () => {
  const v = valueRow({ symbol: 'MSFT', valuation_mode: 'market', quantity: 3, avg_price: 380, currency: 'USD', buy_date: '2026-01-15' }, 496, 1.16, 1.16)
  assert.equal(v.manual, false); approx(v.valueEur, 3 * 496 / 1.16, 1e-6)
})

test('byCategory: subtotals, sub-portfolio split, closed excluded, liability nets down', () => {
  const rows = [
    valueRow({ symbol: 'A', valuation_mode: 'market', quantity: 10, avg_price: 100, currency: 'EUR', category: 'Azionario' }, 120, 1, 1),
    valueRow({ symbol: 'MANUAL:mutuo', valuation_mode: 'manual', manual_value: -500, is_liability: true, category: 'Immobiliare' }, null, null, null),
    valueRow({ symbol: 'MANUAL:casa', valuation_mode: 'manual', manual_value: 2000, category: 'Immobiliare' }, null, null, null),
    valueRow({ symbol: 'SUB', valuation_mode: 'market', quantity: 5, avg_price: 100, currency: 'EUR', category: 'Portafogli Figli' }, 110, 1, 1),
    { ...valueRow({ symbol: 'OLD', valuation_mode: 'market', quantity: 1, avg_price: 1, currency: 'EUR', category: 'Azionario' }, 2, 1, 1), closed: true },
  ]
  const g = byCategory(rows)
  approx(g.cats['Azionario'].valueEur, 1200)          // closed OLD excluded
  approx(g.cats['Immobiliare'].valueEur, 1500)        // 2000 - 500 liability
  approx(g.main.valueEur, 1200 + 1500)                // ex sub-portfolio
  approx(g.sub.valueEur, 550)                          // Portafogli Figli apart
})

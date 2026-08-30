// Options math (mirror of worker/app/options.py) — BS probabilities + structure
// payoff/breakeven/POP. Descriptive (risk-neutral odds), never a forecast.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  normCdf, probAbove, probBelow, verticalSpread, structurePnl, probabilityOfProfit, singleLeg,
} from '../src/lib/options.js'

const approx = (a, b, tol = 1e-4) => assert.ok(Math.abs(a - b) <= tol, `${a} ≈ ${b}`)

test('normCdf + probAbove/probBelow are a coherent risk-neutral pair', () => {
  approx(normCdf(0), 0.5)
  const pa = probAbove(100, 100, 1, 0, 0.2)       // ATM, r=0 → d2 = -0.1
  approx(pa, normCdf(-0.1))
  approx(probBelow(100, 100, 1, 0, 0.2), 1 - pa)
  assert.equal(probAbove(100, 100, 0, 0, 0.2), null)   // T=0 → n/d
  assert.equal(probAbove(100, 100, 1, 0, 0), null)     // sigma=0 → n/d
})

test('call debit vertical: net/maxLoss/maxGain/breakeven/side', () => {
  const m = verticalSpread('call', 100, 5, 110, 2)   // long 100 @5, short 110 @2
  approx(m.netCost, 3)                                 // debit
  approx(m.maxLoss, 3)
  approx(m.maxGain, 7)                                 // width 10 − debit 3
  approx(m.breakeven, 103)                             // lower strike + |net|
  assert.equal(m.profitSide, 'above')
})

test('structurePnl at expiry matches the payoff at key points', () => {
  const m = verticalSpread('call', 100, 5, 110, 2)
  approx(structurePnl(m.legs, 100), -3)               // both worthless → lose the debit
  approx(structurePnl(m.legs, 110), 7)                // max gain at/above short strike
  approx(structurePnl(m.legs, 103), 0)                // breakeven
})

test('probabilityOfProfit uses the breakeven and profit side', () => {
  const m = verticalSpread('call', 100, 5, 110, 2)
  const pop = probabilityOfProfit(m, 100, 1, 0, 0.2)
  approx(pop, probAbove(100, m.breakeven, 1, 0, 0.2))
  assert.equal(probabilityOfProfit({ breakeven: null }, 100, 1, 0, 0.2), null)
})

test('singleLeg long call payoff', () => {
  const leg = singleLeg('call', 'long', 100, 5)
  approx(structurePnl(leg.legs || [leg], 108) ?? structurePnl([leg], 108), 3)  // (108-100)-5
})

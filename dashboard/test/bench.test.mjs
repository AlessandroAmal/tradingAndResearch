// Frontend math tests — lib/bench (mirror of worker/app/decision/bench.py).
// Run via `npm test` (esbuild-bundled, node:test). No new deps.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { rMultiple, breakevenWinrate, betMath, scenarioLadder, bsPrice, optionIllustration, verdict, impliedOnLevels } from '../src/lib/bench.js'

const approx = (a, b, tol = 1e-6) => assert.ok(Math.abs(a - b) <= tol, `${a} ≈ ${b}`)

test('R:R and cost-adjusted break-even win rate', () => {
  approx(rMultiple(100, 98, 106), 3)
  approx(breakevenWinrate(2, 6, 0), 0.25)
  approx(breakevenWinrate(1000, 3000, 200), 0.30)   // costs raise the bar
})

test('betMath bundles currency + ratio with point value', () => {
  const m = betMath({ entry: 2000, stop: 1980, target: 2060, size: 1, multiplier: 100, spreadBps: 5 })
  approx(m.riskAmount, 2000); approx(m.rewardAmount, 6000); approx(m.rr, 3)
  approx(m.costAmount, 100); approx(m.breakevenWinrate, 0.2625); approx(m.breakevenWinrateNoCost, 0.25)
})

test('scenario ladder: stop/target/gap + sign by direction', () => {
  const rows = scenarioLadder({ entry: 100, stop: 98, target: 106, atr: 2, direction: 'long', size: 1, multiplier: 100 })
  const labels = rows.map((r) => r.label)
  assert.ok(labels.includes('stop') && labels.includes('target'))
  assert.ok(rows.some((r) => r.kind === 'gap'))
  approx(rows.find((r) => r.label === 'stop').pnl, -200)
  const gap = rows.find((r) => r.kind === 'gap')
  assert.ok(gap.pnl < -200)   // gap-through-stop is worse than the planned stop
})

test('BS put-call parity + defined-risk option illustration', () => {
  const S = 100, K = 100, T = 0.25, r = 0.04, sig = 0.2
  const c = bsPrice('call', S, K, T, r, sig), p = bsPrice('put', S, K, T, r, sig)
  approx(c - p, S - K * Math.exp(-r * T), 1e-9)
  const ill = optionIllustration({ spot: 100, strike: 100, direction: 'long', T: 0.1, r: 0.04, sigma: 0.3, target: 110, contractSize: 1 })
  assert.equal(ill.kind, 'call'); approx(ill.maxLoss, ill.premium); assert.ok(ill.thetaDaily < 0)
})

test('verdict states edge + thesis, never buy/sell', () => {
  const v = verdict(0.34, 0.41)
  approx(v.edge, 0.07, 1e-9)
  const blob = (v.text + v.disclaimer).toLowerCase()
  assert.ok(blob.includes('tua') && !blob.includes('compra') && !blob.includes('vendi'))
  assert.equal(verdict(null, 0.4).edge, null)
})

test('impliedOnLevels: target/stop probs from nearest-expiry IV, direction-aware', () => {
  const implied = { spot: 100, risk_free_rate: 0, horizons: [{ available: true, atm_iv: 0.2, days_to_expiry: 30 }] }
  const r = impliedOnLevels({ implied, target: 105, stop: 95, horizonDays: 30, direction: 'long' })
  assert.ok(r.probTarget > 0 && r.probTarget < 1)
  assert.ok(r.probStop > 0 && r.probStop < 1)
  // short flips: prob of reaching a lower target rises
  const rs = impliedOnLevels({ implied, target: 95, stop: 105, horizonDays: 30, direction: 'short' })
  assert.ok(rs.probTarget > 0 && rs.probTarget < 1)
})

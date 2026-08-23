// Frontend math tests — lib/expectancy (mirror of worker/app/expectancy.py).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { expectancyStats, kellyAdjusted, riskOfRuin, wilsonCi, tradeR } from '../src/lib/expectancy.js'

const approx = (a, b, tol = 1e-6) => assert.ok(Math.abs(a - b) <= tol, `${a} ≈ ${b}`)
const mk = (rs) => rs.map((r) => ({ r, pnl: r * 100 }))

test('tradeR from pnl and risk', () => {
  approx(tradeR(100, 98, 600, 1, 100), 3)
  assert.equal(tradeR(100, null, 600, 1, 100), null)
})

test('expectancy stats + threshold', () => {
  const s = expectancyStats(mk([2, 2, 2, 2, 2, 2, -1, -1, -1, -1]))
  approx(s.winRate, 0.6); approx(s.avgWinR, 2); approx(s.avgLossR, 1)
  approx(s.expectancyR, 0.8); approx(s.profitFactor, 3)
  assert.equal(s.sufficient, false)   // n=10 < 20
  assert.ok(s.winRateCi[0] < 0.6 && s.winRateCi[1] > 0.6)
})

test('wilson CI bounded', () => {
  const [lo, hi] = wilsonCi(15, 30)
  assert.ok(lo >= 0 && lo < 0.5 && hi > 0.5 && hi <= 1)
  assert.equal(wilsonCi(0, 0), null)
})

test('Kelly uses LOWER bound and flags unproven at small n', () => {
  const small = expectancyStats(mk([2, 2, 2, 2, 2, 2, -1, -1, -1, -1]))
  const ka = kellyAdjusted(small)
  assert.equal(ka.proven, false)
  assert.ok(ka.kellyLower < ka.kellyMean)   // uncertainty penalty
  const big = expectancyStats(mk([...Array(60).fill(2), ...Array(40).fill(-1)]))
  const kb = kellyAdjusted(big)
  assert.equal(kb.proven, true)
  assert.ok(kb.quarterKelly < kb.halfKelly && kb.halfKelly <= kb.kellyLower)
})

test('risk of ruin monotonic in risk fraction', () => {
  const lo = riskOfRuin({ winRate: 0.55, rr: 1, riskFrac: 0.01, nRuns: 2000 })
  const hi = riskOfRuin({ winRate: 0.55, rr: 1, riskFrac: 0.05, nRuns: 2000 })
  assert.ok(lo >= 0 && hi <= 1 && hi > lo)
  assert.equal(riskOfRuin({ winRate: 0.5, rr: 0, riskFrac: 0.01 }), null)
})

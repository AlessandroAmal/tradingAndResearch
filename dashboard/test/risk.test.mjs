// Risk math (mirror of worker/app/risk.py) — sizing, open risk, R, P&L, breaches.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  positionSize, openRisk, pctOfAccount, rMultiple, unrealizedPnl,
  stopBreached, daysUntil, evaluatePosition,
} from '../src/lib/risk.js'

const approx = (a, b, tol = 1e-6) => assert.ok(Math.abs(a - b) <= tol, `${a} ≈ ${b}`)

test('positionSize risks exactly riskPct of the account', () => {
  // 1% of 100000 = 1000; stop distance 2 → 500 units risk exactly 1000
  const size = positionSize(100000, 1, 100, 98)
  approx(size, 500)
  approx(openRisk(100, 98, size), 1000)
  approx(pctOfAccount(1000, 100000), 1)
  assert.equal(positionSize(100000, 1, 100, null), null)   // no stop → null
  assert.equal(positionSize(100000, 1, 100, 100), null)    // zero distance → null
})

test('positionSize honours the contract multiplier', () => {
  approx(positionSize(100000, 1, 100, 98, 10), 50)         // perUnit 2×10=20 → 1000/20
})

test('rMultiple = reward/risk', () => {
  approx(rMultiple(100, 98, 106), 3)                        // risk 2, reward 6
  assert.equal(rMultiple(100, null, 106), null)
  assert.equal(rMultiple(100, 100, 106), null)             // zero risk
})

test('unrealizedPnl respects side and multiplier', () => {
  approx(unrealizedPnl(110, 100, 5, 'long'), 50)
  approx(unrealizedPnl(110, 100, 5, 'short'), -50)
  approx(unrealizedPnl(110, 100, 5, 'long', 10), 500)
  assert.equal(unrealizedPnl(null, 100, 5, 'long'), null)
})

test('stopBreached by side', () => {
  assert.equal(stopBreached(97, 98, 'long'), true)          // long: price ≤ stop
  assert.equal(stopBreached(99, 98, 'long'), false)
  assert.equal(stopBreached(103, 102, 'short'), true)       // short: price ≥ stop
  assert.equal(stopBreached(null, 98, 'long'), false)       // unknown price → not breached
})

test('daysUntil floors to whole days', () => {
  const now = Date.parse('2026-01-01T00:00:00Z')
  assert.equal(daysUntil('2026-01-11', now), 10)
  assert.equal(daysUntil(null, now), null)
})

test('evaluatePosition flags breaches', () => {
  const now = Date.parse('2026-01-01T00:00:00Z')
  const r = evaluatePosition(
    { entry: 100, stop: 90, target: 130, size: 200, side: 'long', deadline: '2026-01-03' },
    { current: 88, multiplier: 1, accountSize: 100000, maxRiskPerTradePct: 1, warnDays: 5, nowMs: now })
  approx(r.openRisk, 2000)                  // |100-90|×200
  approx(r.openRiskPct, 2)                   // 2% > 1% limit
  assert.equal(r.riskPerTradeBreached, true)
  assert.equal(r.stopBreached, true)         // 88 ≤ 90
  approx(r.rMultiple, 3)                      // 30/10
  assert.equal(r.deadlineNear, true)         // 2 days ≤ 5
  approx(r.pnl, -2400)                        // (88-100)×200
})

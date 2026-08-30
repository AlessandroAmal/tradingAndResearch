// Pre-trade gate (mirror of worker/app/gate.py + discipline). Validates discipline
// & risk, NEVER direction. Tests the kill-switch helpers + gate warnings.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  consecutiveLosses, cooldownHit, trendConflict, evaluateGate,
  RULE_COUNTERTREND_SHORT, RULE_COUNTERTREND_LONG,
} from '../src/lib/gate.js'

test('consecutiveLosses counts the newest-first streak, stops at a win', () => {
  assert.equal(consecutiveLosses([{ pnl: -1 }, { pnl: -5 }, { pnl: 3 }, { pnl: -2 }]), 2)
  assert.equal(consecutiveLosses([{ realized_pnl: 4 }]), 0)   // win first → 0
  assert.equal(consecutiveLosses([]), 0)
})

test('cooldownHit fires within the window for same symbol+side', () => {
  const now = Date.parse('2026-01-02T00:00:00Z')
  const stops = [{ symbol: 'GC=F', side: 'long', closed_at: '2026-01-01T12:00:00Z' }]
  const hit = cooldownHit(stops, 'GC=F', 'long', now, 24)
  assert.ok(hit && hit.hoursAgo <= 24)
  assert.equal(cooldownHit(stops, 'GC=F', 'short', now, 24), null)   // other side
  assert.equal(cooldownHit(stops, 'GC=F', 'long', now, 6), null)     // outside 6h window
})

test('trendConflict flags counter-trend entries only', () => {
  const up = { ma: [{ period: 200, above: true }, { period: 50, above: true }] }
  const down = { ma: [{ period: 200, above: false }, { period: 50, above: false }] }
  assert.equal(trendConflict('short', up), RULE_COUNTERTREND_SHORT)
  assert.equal(trendConflict('long', down), RULE_COUNTERTREND_LONG)
  assert.equal(trendConflict('long', up), null)         // aligned → no flag
  assert.equal(trendConflict('long', null), null)
})

const BASE = {
  symbol: 'GC=F', side: 'long', entry: 100, size: 500, multiplier: 1,
  accountSize: 100000, maxRiskPerTradePct: 1, maxPortfolioHeatPct: 6,
  maxConcurrentPositions: 3, rrMin: 1.5,
}

test('missing stop is a BLOCKING warning', () => {
  const r = evaluateGate({ ...BASE, stop: null, target: 130 })
  assert.equal(r.hasBlockingWarnings, true)
  assert.ok(r.warnings.some((w) => w.code === 'stop_missing' && w.severity === 'block'))
})

test('over-limit risk and low R/R are (non-blocking) warnings', () => {
  const r = evaluateGate({ ...BASE, stop: 90, target: 105, size: 500 })  // risk 10×500=5000=5% > 1%
  assert.equal(r.hasBlockingWarnings, false)
  assert.ok(r.warnings.some((w) => w.code === 'risk_per_trade'))
  assert.ok(r.warnings.some((w) => w.code === 'rr_low'))          // R/R 0.5 < 1.5
  assert.ok(r.metrics.riskPct > 1 && r.caveat)
})

test('a clean setup within limits has no blocking warning', () => {
  const r = evaluateGate({ ...BASE, stop: 99.6, target: 101, size: 500 }) // risk 0.4×500=200=0.2%
  assert.equal(r.hasBlockingWarnings, false)
  assert.ok(!r.warnings.some((w) => w.code === 'risk_per_trade'))
})

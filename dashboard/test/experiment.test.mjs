// Frontend math tests — lib/experiment (mirror of worker/app/experiment/aggregate.py).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { aggregate, flatten } from '../src/lib/experiment.js'

const approx = (a, b, tol = 1e-6) => assert.ok(Math.abs(a - b) <= tol, `${a} ≈ ${b}`)
const closed = (delay, ret) => ({
  status: 'closed', symbol: 'GC=F', entry: 100,
  entry_conditions: { event: 'US CPI', delay_min: delay, horizon: 'eod', direction: 'long', return_pct: ret, surprise: { direction: 'positive' } },
})

test('aggregate by delay with threshold + gating', () => {
  const pos = [closed(5, 0.01), closed(5, 0.02), closed(5, -0.01), closed(30, 0.005), closed(30, -0.002)]
  const agg = aggregate(pos, ['symbol', 'delay_min', 'horizon'], { minSample: 3 })
  const by = Object.fromEntries(agg.map((c) => [c.group.delay_min, c]))
  assert.equal(by[5].n, 3); assert.equal(by[5].sufficient, true)
  approx(by[5].pctPositive, 2 / 3)
  approx(by[5].meanReturn, (0.01 + 0.02 - 0.01) / 3)
  assert.equal(by[30].n, 2); assert.equal(by[30].sufficient, false)   // below minSample
})

test('open positions are ignored; only closed with a return count', () => {
  assert.equal(aggregate([{ status: 'open', symbol: 'x' }], ['symbol']).length, 0)
})

test('flatten reads return_pct or derives from realized_pnl', () => {
  const f = flatten({ status: 'closed', symbol: 'X', entry: 100, realized_pnl: 5, entry_conditions: { delay_min: 5 } })
  approx(f.return_pct, 0.05)
})

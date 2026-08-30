// Thematic concentration (mirror of worker/app/concentration.py) — flags when
// several holdings share a theme (correlated, not diversified).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { themeConcentration, themesBySymbol } from '../src/lib/concentration.js'

const THEMES = { NVDA: ['ai_datacenter'], MSFT: ['ai_datacenter'], TSLA: ['ev'] }

test('themeConcentration flags a shared theme with weight + sorted symbols', () => {
  const pos = [{ symbol: 'NVDA', notional: 3000 }, { symbol: 'MSFT', notional: 1000 }, { symbol: 'TSLA', notional: 1000 }]
  const out = themeConcentration(pos, THEMES)
  const ai = out.find((t) => t.theme === 'ai_datacenter')
  assert.equal(ai.positions, 2)
  assert.deepEqual(ai.symbols, ['MSFT', 'NVDA'])       // sorted
  assert.equal(ai.notional, 4000)
  assert.ok(Math.abs(ai.weight - 4000 / 5000) < 1e-9)  // of total notional
  assert.equal(ai.concentrated, true)                   // ≥ 2 symbols
  const ev = out.find((t) => t.theme === 'ev')
  assert.equal(ev.concentrated, false)                  // single symbol
})

test('a single-symbol theme is not concentrated; concentrated sorts first', () => {
  const out = themeConcentration([{ symbol: 'NVDA', notional: 1 }, { symbol: 'MSFT', notional: 1 }, { symbol: 'TSLA', notional: 9 }], THEMES)
  assert.equal(out[0].theme, 'ai_datacenter')           // concentrated first despite lower notional
})

test('themesBySymbol reads the instruments themes column', () => {
  const map = themesBySymbol([
    { symbol: 'NVDA', themes: ['ai_datacenter'] },
    { symbol: 'X', themes: null },
  ])
  assert.deepEqual(map.NVDA, ['ai_datacenter'])
  assert.ok(!map.X || map.X.length === 0)
})

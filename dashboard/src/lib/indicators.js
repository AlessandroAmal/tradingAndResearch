// Client-side mirror of worker/app/indicators.py for display.
// Returns null on insufficient data so the UI can degrade gracefully.

export function sma(closes, period) {
  if (period <= 0 || closes.length < period) return null
  const w = closes.slice(-period)
  return w.reduce((a, b) => a + b, 0) / period
}

export function dailyChange(closes) {
  if (closes.length < 2) return { abs: null, pct: null }
  const prev = closes[closes.length - 2]
  const last = closes[closes.length - 1]
  const abs = last - prev
  return { abs, pct: prev ? (abs / prev) * 100 : null }
}

export function distanceFromMaPct(closes, period) {
  const ma = sma(closes, period)
  if (ma === null || closes.length === 0 || ma === 0) return null
  return ((closes[closes.length - 1] - ma) / ma) * 100
}

export function atr(highs, lows, closes, period = 14) {
  const n = closes.length
  if (n < period + 1 || highs.length !== n || lows.length !== n) return null
  const trs = []
  for (let i = 1; i < n; i++) {
    trs.push(
      Math.max(
        highs[i] - lows[i],
        Math.abs(highs[i] - closes[i - 1]),
        Math.abs(lows[i] - closes[i - 1]),
      ),
    )
  }
  const w = trs.slice(-period)
  return w.reduce((a, b) => a + b, 0) / period
}

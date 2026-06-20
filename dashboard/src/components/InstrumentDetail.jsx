import { useEffect, useMemo, useState } from 'react'
import { fetchPrices } from '../api/data'
import { atr, dailyChange, distanceFromMaPct } from '../lib/indicators'
import { fmtNum, fmtPct } from '../lib/format'
import PriceChart from './PriceChart'

const MA_PERIODS = [20, 50, 200]

// Detail for one instrument: chart + daily change/% + distance-from-MA + ATR.
export default function InstrumentDetail({ instrument }) {
  const [bars, setBars] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!instrument) return
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchPrices(instrument.id, 250).then(({ data, error }) => {
      if (cancelled) return
      if (error) {
        setError(error.message)
        setBars([])
      } else {
        // API returns newest-first; charts/indicators want ascending.
        setBars((data || []).slice().reverse())
      }
      setLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [instrument])

  const stats = useMemo(() => {
    const closes = bars.map((b) => b.close).filter((c) => c != null)
    const highs = bars.map((b) => b.high)
    const lows = bars.map((b) => b.low)
    const { abs, pct } = dailyChange(closes)
    return {
      last: closes.at(-1) ?? null,
      changeAbs: abs,
      changePct: pct,
      ma: MA_PERIODS.map((p) => ({ p, dist: distanceFromMaPct(closes, p) })),
      atr14: atr(highs, lows, closes, 14),
    }
  }, [bars])

  if (!instrument) {
    return (
      <section className="panel">
        <p className="muted">Select an instrument from the watchlist.</p>
      </section>
    )
  }

  const up = (stats.changePct ?? 0) >= 0

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>
          {instrument.symbol}{' '}
          <span className="muted">{instrument.name || ''}</span>
        </h2>
        {loading && <span className="muted">loading…</span>}
      </header>

      {error && <p className="error">Price feed unavailable — {error}</p>}

      <div className="stat-grid">
        <Stat label="Last" value={fmtNum(stats.last)} />
        <Stat
          label="Daily Δ"
          value={fmtNum(stats.changeAbs)}
          className={up ? 'pos' : 'neg'}
        />
        <Stat
          label="Daily %"
          value={fmtPct(stats.changePct)}
          className={up ? 'pos' : 'neg'}
        />
        <Stat label="ATR(14)" value={fmtNum(stats.atr14)} />
        {stats.ma.map((m) => (
          <Stat
            key={m.p}
            label={`vs MA${m.p}`}
            value={fmtPct(m.dist)}
            className={(m.dist ?? 0) >= 0 ? 'pos' : 'neg'}
          />
        ))}
      </div>

      {bars.length > 0 ? (
        <PriceChart bars={bars} />
      ) : (
        !loading && !error && <p className="muted">No price history yet.</p>
      )}
    </section>
  )
}

function Stat({ label, value, className = '' }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className={`stat-value ${className}`}>{value}</span>
    </div>
  )
}

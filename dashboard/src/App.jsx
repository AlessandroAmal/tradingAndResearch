import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchInstruments,
  fetchPrices,
  fetchUpcomingEvents,
  fetchPositions,
} from './api/data'
import { isConfigured } from './lib/supabase'
import { dailyChange } from './lib/indicators'
import Watchlist from './components/Watchlist'
import InstrumentDetail from './components/InstrumentDetail'
import Catalysts from './components/Catalysts'
import PositionForm from './components/PositionForm'
import PositionsList from './components/PositionsList'
import BriefingPanel from './components/BriefingPanel'
import Guide from './pages/Guide'

const REFRESH_MS = 60_000

export default function App() {
  const [instruments, setInstruments] = useState([])
  const [watch, setWatch] = useState([]) // instruments + last/changePct
  const [events, setEvents] = useState([])
  const [positions, setPositions] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [errors, setErrors] = useState({})
  const [nowMs, setNowMs] = useState(Date.now())
  const [view, setView] = useState('dashboard') // 'dashboard' | 'guide' (state only)

  // tick for live countdowns (state only — no browser storage)
  useEffect(() => {
    const t = setInterval(() => setNowMs(Date.now()), 30_000)
    return () => clearInterval(t)
  }, [])

  const loadAll = useCallback(async () => {
    setLoading(true)
    const nextErrors = {}

    const inst = await fetchInstruments()
    if (inst.error) nextErrors.instruments = inst.error.message
    const instrumentRows = inst.data || []
    setInstruments(instrumentRows)
    if (!selectedId && instrumentRows.length) setSelectedId(instrumentRows[0].id)

    // Per-instrument last close + daily change (small N).
    const withChange = await Promise.all(
      instrumentRows.map(async (i) => {
        const { data, error } = await fetchPrices(i.id, 2)
        if (error || !data || data.length === 0) {
          return { ...i, last: null, changePct: null }
        }
        const closes = data.slice().reverse().map((r) => r.close)
        const last = closes.at(-1)
        const { pct } = dailyChange(closes)
        return { ...i, last, changePct: pct }
      }),
    )
    setWatch(withChange)

    const ev = await fetchUpcomingEvents(25)
    if (ev.error) nextErrors.events = ev.error.message
    setEvents(ev.data || [])

    const pos = await fetchPositions('open')
    if (pos.error) nextErrors.positions = pos.error.message
    setPositions(pos.data || [])

    setErrors(nextErrors)
    setLoading(false)
  }, [selectedId])

  useEffect(() => {
    loadAll()
    const t = setInterval(loadAll, REFRESH_MS)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const selected = useMemo(
    () => instruments.find((i) => i.id === selectedId) || null,
    [instruments, selectedId],
  )

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1>Trading & Research Command Center</h1>
          <p className="muted small">
            Read-only cockpit · information &amp; risk management · not financial advice
          </p>
        </div>
        <div className="topbar-actions">
          <nav className="nav" aria-label="Sezioni">
            <button
              className={`nav-btn ${view === 'dashboard' ? 'active' : ''}`}
              onClick={() => setView('dashboard')}
              aria-current={view === 'dashboard' ? 'page' : undefined}
            >
              Dashboard
            </button>
            <button
              className={`nav-btn ${view === 'guide' ? 'active' : ''}`}
              onClick={() => setView('guide')}
              aria-current={view === 'guide' ? 'page' : undefined}
            >
              Guida
            </button>
          </nav>
          {view === 'dashboard' && (
            <button onClick={loadAll} disabled={loading}>
              {loading ? 'Refreshing…' : 'Refresh'}
            </button>
          )}
        </div>
      </header>

      {view === 'dashboard' && !isConfigured && (
        <div className="banner error">
          Supabase is not configured. Copy <code>dashboard/.env.example</code> to{' '}
          <code>.env</code> and set <code>VITE_SUPABASE_URL</code> /{' '}
          <code>VITE_SUPABASE_ANON_KEY</code>.
        </div>
      )}

      {view === 'guide' ? (
        <Guide />
      ) : (
      <main className="grid">
        <div className="col-left">
          <Watchlist
            rows={watch}
            selected={selectedId}
            onSelect={setSelectedId}
            loading={loading}
            error={errors.instruments}
          />
          <Catalysts
            events={events}
            loading={loading}
            error={errors.events}
            nowMs={nowMs}
          />
        </div>

        <div className="col-mid">
          <BriefingPanel />
          <InstrumentDetail instrument={selected} />
        </div>

        <div className="col-right">
          <PositionForm
            instruments={instruments}
            onSaved={loadAll}
          />
          <section className="panel">
            <header className="panel-head">
              <h2>Open positions</h2>
            </header>
            {errors.positions && (
              <p className="error">Positions unavailable — {errors.positions}</p>
            )}
            <PositionsList positions={positions} nowMs={nowMs} />
          </section>
        </div>
      </main>
      )}
    </div>
  )
}

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchInstruments,
  fetchPrices,
  fetchUpcomingEvents,
  fetchPositions,
  fetchRiskSettings,
} from './api/data'
import { isConfigured } from './lib/supabase'
import { refresh as apiRefresh, apiConfigured } from './api/control'
import { dailyChange } from './lib/indicators'
import Watchlist from './components/Watchlist'
import InstrumentDetail from './components/InstrumentDetail'
import Catalysts from './components/Catalysts'
import TradeGate from './components/TradeGate'
import PositionsTable from './components/PositionsTable'
import SizingCalculator from './components/SizingCalculator'
import BriefingPanel from './components/BriefingPanel'
import KeyFigures from './components/KeyFigures'
import StatusStrip from './components/StatusStrip'
import Guide from './pages/Guide'
import Journal from './pages/Journal'
import OptionsDesk from './pages/OptionsDesk'
import Alerts from './pages/Alerts'
import DecisionBoard from './pages/DecisionBoard'
import Backtest from './pages/Backtest'

const REFRESH_MS = 60_000

export default function App() {
  const [instruments, setInstruments] = useState([])
  const [watch, setWatch] = useState([]) // instruments + last/changePct
  const [events, setEvents] = useState([])
  const [positions, setPositions] = useState([])
  const [riskSettings, setRiskSettings] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [refreshErr, setRefreshErr] = useState(null)
  const [errors, setErrors] = useState({})
  const [nowMs, setNowMs] = useState(Date.now())
  // Information architecture: primary groups + a trading sub-tab (state only).
  const [primary, setPrimary] = useState('mercati')     // 'mercati' | 'trading' | 'guida'
  const [tradingTab, setTradingTab] = useState('risk')  // 'risk' | 'journal' | 'options'

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

    const rs = await fetchRiskSettings()
    if (rs.error) nextErrors.risk = rs.error.message
    setRiskSettings(rs.data || null)

    setErrors(nextErrors)
    setLoading(false)
  }, [selectedId])

  // "Aggiorna": if the local control API is configured, run the FREE refresh
  // (prices + macro + calendar + board rebuild, NO AI) then re-read Supabase.
  // Without the API it just re-reads what the worker last wrote.
  const handleRefresh = useCallback(async () => {
    setRefreshErr(null)
    if (apiConfigured) {
      setRefreshing(true)
      const { error } = await apiRefresh()
      setRefreshing(false)
      if (error) setRefreshErr(error.message)
    }
    await loadAll()
  }, [loadAll])

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

  // Maps for the risk views: latest price + contract multiplier by symbol.
  const priceBySymbol = useMemo(
    () => Object.fromEntries(watch.map((w) => [w.symbol, w.last])),
    [watch],
  )
  const multiplierBySymbol = useMemo(
    () =>
      Object.fromEntries(
        instruments.map((i) => [i.symbol, Number(i.contract_multiplier) || 1]),
      ),
    [instruments],
  )

  const navItem = (key, label) => (
    <button
      className={`nav-btn ${primary === key ? 'active' : ''}`}
      onClick={() => setPrimary(key)}
      aria-current={primary === key ? 'page' : undefined}
    >
      {label}
    </button>
  )

  const tradingTabBtn = (key, label) => (
    <button
      className={`nav-btn ${tradingTab === key ? 'active' : ''}`}
      onClick={() => setTradingTab(key)}
      aria-current={tradingTab === key ? 'page' : undefined}
    >
      {label}
    </button>
  )

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1>Trading &amp; Research Command Center</h1>
          <p className="muted small">
            Cockpit read-only · informazione &amp; gestione del rischio · non è consulenza finanziaria
          </p>
        </div>
        <div className="topbar-actions">
          <nav className="nav" aria-label="Sezioni">
            {navItem('mercati', 'Mercati')}
            {navItem('trading', 'Trading')}
            {navItem('guida', 'Guida')}
          </nav>
          {primary !== 'guida' && (
            <button className="primary" onClick={handleRefresh} disabled={loading || refreshing}>
              {refreshing ? 'Aggiornamento in corso…' : loading ? 'Aggiorno…' : 'Aggiorna'}
            </button>
          )}
        </div>
      </header>

      {primary !== 'guida' && !isConfigured && (
        <div className="banner error">
          Supabase non configurato. Copia <code>dashboard/.env.example</code> in{' '}
          <code>.env</code> e imposta <code>VITE_SUPABASE_URL</code> /{' '}
          <code>VITE_SUPABASE_ANON_KEY</code>.
        </div>
      )}

      {primary !== 'guida' && refreshing && (
        <div className="banner">
          Aggiornamento dati in corso (prezzi · macro · calendario · decision board) — può
          richiedere qualche minuto…
        </div>
      )}
      {primary !== 'guida' && refreshErr && (
        <div className="banner error">Aggiornamento non riuscito — {refreshErr}</div>
      )}

      {primary === 'guida' && <Guide />}

      {primary !== 'guida' && (
        <StatusStrip
          positions={positions}
          priceBySymbol={priceBySymbol}
          multiplierBySymbol={multiplierBySymbol}
          settings={riskSettings}
          events={events}
          nowMs={nowMs}
        />
      )}

      {primary === 'mercati' && (
        <main className="grid grid-markets">
          <div className="col-left">
            <Watchlist
              rows={watch}
              selected={selectedId}
              onSelect={setSelectedId}
              loading={loading}
              error={errors.instruments}
            />
            <Catalysts events={events} loading={loading} error={errors.events} nowMs={nowMs} />
            <KeyFigures />
          </div>
          <div className="col-main">
            <BriefingPanel />
            <InstrumentDetail instrument={selected} />
          </div>
        </main>
      )}

      {primary === 'trading' && (
        <>
          <nav className="nav subnav" aria-label="Sezione trading">
            {tradingTabBtn('risk', 'Posizioni & Rischio')}
            {tradingTabBtn('decision', 'Decision board')}
            {tradingTabBtn('backtest', 'Ricerca')}
            {tradingTabBtn('journal', 'Journal')}
            {tradingTabBtn('options', 'Options')}
            {tradingTabBtn('alerts', 'Alert')}
          </nav>

          {tradingTab === 'risk' && (
            <main className="grid grid-trading">
              <div className="col-left">
                <SizingCalculator instruments={instruments} settings={riskSettings} />
                <TradeGate
                  instruments={instruments}
                  settings={riskSettings}
                  positions={positions}
                  priceBySymbol={priceBySymbol}
                  multiplierBySymbol={multiplierBySymbol}
                  events={events}
                  onSaved={loadAll}
                />
              </div>
              <div className="col-main">
                <section className="panel">
                  <header className="panel-head">
                    <h2>Posizioni aperte</h2>
                    {loading && <span className="muted small">aggiorno…</span>}
                  </header>
                  {errors.positions && (
                    <p className="error">Posizioni non disponibili — {errors.positions}</p>
                  )}
                  {errors.risk && (
                    <p className="error small">
                      Impostazioni di rischio non disponibili — {errors.risk} (applica la 0007 + seed)
                    </p>
                  )}
                  <PositionsTable
                    positions={positions}
                    priceBySymbol={priceBySymbol}
                    multiplierBySymbol={multiplierBySymbol}
                    settings={riskSettings}
                    nowMs={nowMs}
                  />
                </section>
              </div>
            </main>
          )}

          {tradingTab === 'decision' && <DecisionBoard />}

          {tradingTab === 'backtest' && <Backtest />}

          {tradingTab === 'journal' && (
            <Journal instruments={instruments} positions={positions} />
          )}

          {tradingTab === 'options' && <OptionsDesk />}

          {tradingTab === 'alerts' && <Alerts instruments={instruments} />}
        </>
      )}
    </div>
  )
}

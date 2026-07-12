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
import MarketsOverview from './components/MarketsOverview'
import { PaperPositions } from './components/PaperMonitor'
import ConcentrationWarning from './components/ConcentrationWarning'
import ExperimentResults from './pages/ExperimentResults'
import TabHeader from './components/TabHeader'
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
  const [closedPositions, setClosedPositions] = useState([])
  const [riskSettings, setRiskSettings] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [refreshErr, setRefreshErr] = useState(null)
  const [errors, setErrors] = useState({})
  const [nowMs, setNowMs] = useState(Date.now())
  const [refreshKey, setRefreshKey] = useState(0) // bumped each load -> self-fetching panels re-read
  // Information architecture: primary groups + a trading sub-tab (state only).
  const [primary, setPrimary] = useState('mercati')     // 'mercati' | 'trading' | 'guida'
  const [tradingTab, setTradingTab] = useState('risk')  // 'risk' | 'journal' | 'options'
  const [decisionSymbol, setDecisionSymbol] = useState(null) // opened from the overview

  const openDecision = (sym) => {
    setDecisionSymbol(sym)
    setPrimary('trading')
    setTradingTab('decision')
  }

  // tick for live countdowns (state only — no browser storage)
  useEffect(() => {
    const t = setInterval(() => setNowMs(Date.now()), 30_000)
    return () => clearInterval(t)
  }, [])

  const loadAll = useCallback(async () => {
    setLoading(true)
    setRefreshKey((k) => k + 1) // re-read self-fetching panels (Briefing, Key figures)
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

    // Recently closed positions power the set-aside tracker + the "re-entered a
    // losing direction" guard (both read realized_pnl stamped at close).
    const closed = await fetchPositions('closed')
    setClosedPositions(closed.data || [])

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

  // Paper (test) positions are separate from real risk: they NEVER count in heat.
  const realPositions = useMemo(() => positions.filter((p) => !p.paper), [positions])
  // Manual paper positions EXCLUDE the auto experiment ones (kept separate so
  // the experiment can't pollute the review of the user's own process).
  const paperPositions = useMemo(() => positions.filter((p) => p.paper && !p.experiment), [positions])
  // Recently closed (real + paper) — the discipline guards look at both.
  const recentClosed = useMemo(() => closedPositions || [], [closedPositions])

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
          positions={realPositions}
          priceBySymbol={priceBySymbol}
          multiplierBySymbol={multiplierBySymbol}
          settings={riskSettings}
          events={events}
          nowMs={nowMs}
        />
      )}

      {primary === 'mercati' && (
        <MarketsOverview refreshKey={refreshKey} onOpen={openDecision} nowMs={nowMs} />
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
            <KeyFigures refreshKey={refreshKey} />
          </div>
          <div className="col-main">
            <BriefingPanel refreshKey={refreshKey} />
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
            {tradingTabBtn('experiment', 'Esperimento eventi')}
            {tradingTabBtn('journal', 'Journal')}
            {tradingTabBtn('options', 'Options')}
            {tradingTabBtn('alerts', 'Alert')}
          </nav>

          {tradingTab === 'risk' && (
            <>
              <TabHeader
                title="Posizioni & Rischio"
                purpose="Dimensiona e monitora il rischio. Calcola la size da entry/stop/rischio%; tieni P&L, heat e deadline sotto i tuoi limiti."
                howto={[
                  'Usa la calcolatrice di sizing per ottenere la size dal rischio% scelto.',
                  '“Nuovo trade — checklist” valida i numeri contro le tue regole (warning, non blocchi).',
                  '“Monitora come test” apre una posizione IPOTETICA (paper) — nessun ordine — per il track record.',
                ]}
                onGuide={() => setPrimary('guida')}
              />
              <main className="grid grid-trading">
                <div className="col-left">
                  <SizingCalculator instruments={instruments} settings={riskSettings} priceBySymbol={priceBySymbol} />
                  <TradeGate
                    instruments={instruments}
                    settings={riskSettings}
                    positions={realPositions}
                    closedPositions={recentClosed}
                    priceBySymbol={priceBySymbol}
                    multiplierBySymbol={multiplierBySymbol}
                    events={events}
                    onSaved={loadAll}
                  />
                </div>
                <div className="col-main">
                  <ConcentrationWarning
                    positions={realPositions}
                    priceBySymbol={priceBySymbol}
                    multiplierBySymbol={multiplierBySymbol}
                    instruments={instruments}
                  />
                  <section className="panel">
                    <header className="panel-head">
                      <h2>Posizioni aperte (reali)</h2>
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
                      positions={realPositions}
                      priceBySymbol={priceBySymbol}
                      multiplierBySymbol={multiplierBySymbol}
                      settings={riskSettings}
                      nowMs={nowMs}
                    />
                  </section>
                  <section className="panel">
                    <header className="panel-head">
                      <h2>Posizioni di test (paper)</h2>
                      <span className="muted small">ipotetiche · non contano nel rischio reale</span>
                    </header>
                    <PaperPositions
                      positions={paperPositions}
                      priceBySymbol={priceBySymbol}
                      multiplierBySymbol={multiplierBySymbol}
                      nowMs={nowMs}
                      onChanged={loadAll}
                    />
                  </section>
                </div>
              </main>
            </>
          )}

          {tradingTab === 'decision' && (
            <DecisionBoard
              initialSymbol={decisionSymbol}
              instruments={instruments}
              settings={riskSettings}
              positions={realPositions}
              closedPositions={recentClosed}
              events={events}
              priceBySymbol={priceBySymbol}
              multiplierBySymbol={multiplierBySymbol}
              onSaved={loadAll}
            />
          )}

          {tradingTab === 'backtest' && (
            <>
              <TabHeader title="Ricerca / Backtest"
                purpose="Misura se una regola tecnica ha edge — NON genera segnali."
                howto={[
                  'Guarda il NETTO out-of-sample vs buy&hold (non l’in-sample).',
                  'Lo Sharpe deflazionato sconta il data-snooping (best-of-N).',
                ]}
                onGuide={() => setPrimary('guida')} />
              <Backtest />
            </>
          )}

          {tradingTab === 'experiment' && (
            <>
              <TabHeader title="Esperimento eventi (paper)"
                purpose="Esperimento controllato: apre posizioni di TEST ai vari ritardi dopo i dati USA per MISURARE cosa succede. Read-only, mai un ordine, mai un segnale."
                howto={[
                  'n sempre visibile; sotto soglia = campione insufficiente, non una probabilità.',
                  'Confronta i ritardi (subito vs aspettare) e la direzione della sorpresa.',
                  'Separato dal rischio reale e dalle tue paper manuali.',
                ]}
                onGuide={() => setPrimary('guida')} />
              <ExperimentResults refreshKey={refreshKey} nowMs={nowMs} />
            </>
          )}

          {tradingTab === 'journal' && (
            <>
              <TabHeader title="Journal"
                purpose="Registra ogni trade e impara: la review mostra quali tuoi setup funzionano, con n."
                howto={[
                  'Le posizioni di test chiuse alimentano la review (esito + P&L).',
                  'Con poche voci i pattern sono ipotesi, non conclusioni (n sempre visibile).',
                ]}
                onGuide={() => setPrimary('guida')} />
              <Journal instruments={instruments} positions={positions} />
            </>
          )}

          {tradingTab === 'options' && (
            <>
              <TabHeader title="Options"
                purpose="Struttura coperture e trade con perdita massima, R/R e POP."
                howto={[
                  'POP = probabilità di profitto implicita di QUELLA struttura, non una previsione.',
                  'POP alta di solito = payoff piccolo: leggila con max loss e R/R.',
                ]}
                onGuide={() => setPrimary('guida')} />
              <OptionsDesk />
            </>
          )}

          {tradingTab === 'alerts' && (
            <>
              <TabHeader title="Alert"
                purpose="Notifiche su rischio, eventi, soglie e key-figure."
                howto={['Le regole standing e le soglie sono edge-triggered con cooldown (niente spam).']}
                onGuide={() => setPrimary('guida')} />
              <Alerts instruments={instruments} />
            </>
          )}
        </>
      )}
    </div>
  )
}

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
import SizingCalculator from './components/SizingCalculator'
import BriefingPanel from './components/BriefingPanel'
import KeyFigures from './components/KeyFigures'
import StatusStrip from './components/StatusStrip'
import MarketsOverview from './components/MarketsOverview'
import { PaperPositions } from './components/PaperMonitor'
import PortfolioReal from './components/PortfolioReal'
import ExperimentResults from './pages/ExperimentResults'
import DecisionBench from './pages/DecisionBench'
import Expectancy from './pages/Expectancy'
import Calibration from './pages/Calibration'
import Episodes from './pages/Episodes'
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
  // Information architecture (AUDIT §6): 5 sections + Guida, each answering ONE
  // question. Multi-view sections carry a light in-section sub-nav (state only).
  const [primary, setPrimary] = useState('mercati')     // mercati|asset|decidi|portafoglio|ricerca|guida
  const [portTab, setPortTab] = useState('posizioni')   // posizioni | reale | andamento | alert
  const [ricercaTab, setRicercaTab] = useState('backtest') // backtest | calibrazione | esperimento
  const [decisionSymbol, setDecisionSymbol] = useState(null) // opened from the overview
  const [assetSymbol, setAssetSymbol] = useState(null)       // symbol shown in ASSET (drives the chart)

  const openDecision = (sym) => {
    setDecisionSymbol(sym)
    setAssetSymbol(sym)   // show the chart for it immediately
    setPrimary('asset')
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
        const { data, error } = await fetchPrices(i.id, 5)
        if (error || !data || data.length === 0) {
          return { ...i, last: null, changePct: null }
        }
        // Ascending, dropping null closes: a partial current-day bar (pre-market /
        // not-yet-finalised) can have a null close and must NOT read as "n/d" for
        // a liquid instrument — use the last REAL close.
        const closes = data.slice().reverse().map((r) => r.close).filter((c) => c != null)
        const last = closes.at(-1) ?? null
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
  // Instrument shown in ASSET (for the price chart at the top), synced with the
  // decision board's selected symbol.
  const assetInstrument = useMemo(
    () => instruments.find((i) => i.symbol === assetSymbol) || null,
    [instruments, assetSymbol],
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

  // Generic in-section sub-nav pill (used by Portafoglio and Ricerca).
  const subBtn = (cur, setter) => (key, label) => (
    <button
      key={key}
      className={`nav-btn ${cur === key ? 'active' : ''}`}
      onClick={() => setter(key)}
      aria-current={cur === key ? 'page' : undefined}
    >
      {label}
    </button>
  )
  const portBtn = subBtn(portTab, setPortTab)
  const ricercaBtn = subBtn(ricercaTab, setRicercaTab)

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
            {navItem('asset', 'Asset')}
            {navItem('decidi', 'Decidi')}
            {navItem('portafoglio', 'Portafoglio')}
            {navItem('ricerca', 'Ricerca')}
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
        <PortfolioReal instruments={instruments} priceBySymbol={priceBySymbol} onOpenAsset={openDecision}
          positions={realPositions} multiplierBySymbol={multiplierBySymbol} settings={riskSettings} nowMs={nowMs} />
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

      {primary === 'asset' && (
        <>
          <TabHeader title="Asset — com'è messo questo asset e dove può andare?"
            purpose="Le CONDIZIONI ORA (lancetta, driver macro con freschezza, «cosa ha mosso», tecnica, news, fondamentali) e, sotto, le PROSPETTIVE future (distribuzione multi-orizzonte). Non è una previsione."
            howto={[
              'La lancetta è l’allineamento delle CONDIZIONI attuali, non una probabilità né una previsione.',
              'Il numero calibrato è la probabilità IMPLICITA (opzioni); lo storico è frequenza con n.',
              'Le Prospettive in fondo sono distribuzioni di esiti (opzioni risk-neutral + storico con n effettivo).',
            ]}
            onGuide={() => setPrimary('guida')} />
          {/* Price chart on top — this IS the "com'è messo l'asset" view; it must
              show the candle chart + technicals + news, synced to the board symbol. */}
          <InstrumentDetail instrument={assetInstrument} />
          <DecisionBoard
            initialSymbol={decisionSymbol}
            instruments={instruments}
            settings={riskSettings}
            positions={realPositions}
            closedPositions={recentClosed}
            events={events}
            priceBySymbol={priceBySymbol}
            multiplierBySymbol={multiplierBySymbol}
            onSymbolChange={setAssetSymbol}
            onSaved={loadAll}
          />
        </>
      )}

      {primary === 'decidi' && (
        <>
          <TabHeader title="Decidi — questa scommessa ha senso, e con che struttura entro?"
            purpose="L’aritmetica di UNA scommessa: win-rate di pareggio (costi inclusi) vs odds impliciti, scenari in €, confronto diretta vs opzione. Precompilato: cambia 1-2 campi."
            howto={[
              'I campi sono precompilati (prezzo, stop ~k×ATR, target da R/R, rischio% da config): cambia solo ciò che vuoi.',
              'Il margine è la TUA tesi: gli odds impliciti sono già il mercato.',
              '“Monitora come test” salva la scommessa come paper con lo snapshot.',
            ]}
            onGuide={() => setPrimary('guida')} />
          <DecisionBench
            instruments={instruments} settings={riskSettings}
            positions={realPositions} closedPositions={recentClosed}
            priceBySymbol={priceBySymbol} multiplierBySymbol={multiplierBySymbol}
            events={events} initialSymbol={decisionSymbol} onSaved={loadAll} />
          <details className="section-fold">
            <summary>Options — struttura a rischio definito (catene reali, POP, Greeks)</summary>
            <OptionsDesk />
          </details>
          <details className="section-fold">
            <summary>Sizing calculator (standalone)</summary>
            <SizingCalculator instruments={instruments} settings={riskSettings} priceBySymbol={priceBySymbol} />
          </details>
        </>
      )}

      {primary === 'portafoglio' && (
        <>
          <TabHeader title="Portafoglio — cosa ho e come sto andando davvero?"
            purpose="Le tue posizioni (reali e di test), heat e concentrazione; e la review unificata: expectancy (quantitativa) + pattern del journal (qualitativa)."
            howto={[
              'Le posizioni di test (paper) non contano nel rischio/heat reale.',
              'La review unisce i numeri (win rate, R, Kelly) e i pattern del journal: stessi trade, due letture.',
              'Gli alert sono edge-triggered con cooldown (niente spam).',
            ]}
            onGuide={() => setPrimary('guida')} />
          <nav className="nav subnav" aria-label="Sezione portafoglio">
            {portBtn('posizioni', 'Posizioni & rischio')}
            {portBtn('andamento', 'Andamento & review')}
            {portBtn('alert', 'Alert')}
          </nav>

          {portTab === 'posizioni' && (
            <>
              <p className="muted small">Le posizioni aperte (reali) e la concentrazione tematica vivono nella vista <strong>Portafoglio</strong> in <em>Mercati</em> (filtro «Trade»/«Tutto») — qui restano gli STRUMENTI per aprire e monitorare un trade.</p>
              <main className="grid grid-trading">
                <div className="col-left">
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

          {portTab === 'andamento' && (
            <>
              <Expectancy settings={riskSettings} multiplierBySymbol={multiplierBySymbol} refreshKey={refreshKey} />
              <Journal instruments={instruments} positions={positions} />
            </>
          )}

          {portTab === 'alert' && (
            <Alerts instruments={instruments} />
          )}
        </>
      )}

      {primary === 'ricerca' && (
        <>
          <TabHeader title="Laboratorio — questa mia intuizione ha valore reale? (misuriamola)"
            purpose="UN solo laboratorio di evidenza (avanzato). Scegli l'oggetto dell'analisi qui sotto. Read-only, mai un segnale."
            howto={[
              'Regola tecnica → backtest OOS; Fattore → IC per orizzonte; Evento → cosa fa il prezzo dopo i dati USA; Episodio → pattern pluriennali rari.',
              'La Calibrazione dei FATTORI ricalibra la lancetta di confluenza usata in ASSET (peso ∝ IC solo dei significativi).',
            ]}
            onGuide={() => setPrimary('guida')} />
          {/* Filosofia anti-data-snooping condivisa UNA volta per tutto il laboratorio */}
          <p className="honest-note small">Regola condivisa del laboratorio: ogni analisi mostra sempre <strong>n</strong> (campione), sconta il <strong>data-snooping</strong> (deflazione / correzione per test multipli) e sotto soglia dichiara «campione insufficiente». Nulla qui è un segnale operativo: è misura, non previsione.</p>
          <nav className="nav subnav" aria-label="Oggetto dell'analisi">
            {ricercaBtn('backtest', 'Regola tecnica')}
            {ricercaBtn('calibrazione', 'Fattore (IC)')}
            {ricercaBtn('esperimento', 'Evento')}
            {ricercaBtn('episodi', 'Episodio')}
          </nav>
          {ricercaTab === 'backtest' && <Backtest />}
          {ricercaTab === 'calibrazione' && <Calibration />}
          {ricercaTab === 'esperimento' && (
            <ExperimentResults refreshKey={refreshKey} nowMs={nowMs} />
          )}
          {ricercaTab === 'episodi' && <Episodes />}
        </>
      )}
    </div>
  )
}

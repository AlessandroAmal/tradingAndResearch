import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchProspectsList, fetchProspects, fetchProspectCalibration } from '../api/data'
import { refreshProspects, calibrateProspects, getProspectsStatus, getProspectsCalibrateStatus, apiConfigured } from '../api/control'
import { useJobStatus, runningLabel, doneLabel } from '../lib/useJobStatus'
import { fmtNum, fmtPct } from '../lib/format'
import InfoTip from '../components/InfoTip'

const HLABEL = { '1s': '1 settimana', '1m': '1 mese', '3m': '3 mesi', '6m': '6 mesi', '1a': '1 anno', '5a': '5 anni' }

// PROSPETTIVE — the distribution of outcomes per horizon, from options (risk-
// neutral), conditional history (with effective n), and valuation. NOT a point
// forecast; every number is market odds or a historical frequency with n.
export default function Prospects({ nowMs = Date.now(), initialSymbol = null }) {
  const [symbols, setSymbols] = useState([])
  const [symbol, setSymbol] = useState('')
  const [snap, setSnap] = useState(null)
  const [cal, setCal] = useState(null)
  const [level, setLevel] = useState('')

  // Prefer defaulting to an instrument that actually has rich data (gold), so the
  // first thing shown isn't an empty grid (e.g. DAX has no options chain).
  const PREFERRED = ['GC=F', 'EURUSD=X', '^NDX', 'NVDA']
  useEffect(() => {
    fetchProspectsList().then(({ data }) => {
      const list = data || []
      setSymbols(list)
      // honour the asset opened from ASSET/overview, else a data-rich default
      const wanted = initialSymbol && list.some((r) => r.symbol === initialSymbol) ? initialSymbol : null
      setSymbol((s) => s || wanted || PREFERRED.find((p) => list.some((r) => r.symbol === p)) || list[0]?.symbol || '')
    })
    fetchProspectCalibration().then(({ data }) => setCal(data || null))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  // Follow the parent (ASSET) symbol: when embedded under the decision board and
  // the user switches instrument, the prospects must switch too (not stay on gold).
  useEffect(() => {
    if (initialSymbol && symbols.some((r) => r.symbol === initialSymbol)) setSymbol(initialSymbol)
  }, [initialSymbol, symbols])
  const load = useCallback(() => { if (symbol) fetchProspects(symbol).then(({ data }) => setSnap(data?.snapshot || null)) }, [symbol])
  useEffect(() => { load() }, [load])

  const onRefreshDone = useCallback(() => {
    fetchProspectsList().then(({ data: list }) => setSymbols(list || []))
    load()
  }, [load])
  const onCalibrateDone = useCallback(() => {
    fetchProspectCalibration().then(({ data: c }) => setCal(c || null))
  }, [])
  const refreshJob = useJobStatus(getProspectsStatus, refreshProspects, onRefreshDone)
  const calibrateJob = useJobStatus(getProspectsCalibrateStatus, calibrateProspects, onCalibrateDone)
  const anyRunning = refreshJob.running || calibrateJob.running

  const spot = snap?.spot
  const K = level !== '' && !Number.isNaN(Number(level)) ? Number(level) : null
  const levelRet = K != null && spot ? K / spot - 1 : null
  const calBySym = cal?.results?.[symbol] || null

  return (
    <div className="desk">
      <section className="panel">
        <header className="panel-head">
          <h2>Prospettive multi-orizzonte</h2>
          <span className="muted small">distribuzione di esiti, non una previsione puntuale</span>
        </header>
        <div className="desk-controls">
          {symbols.length > 0 && (
            <label>Strumento
              <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
                {symbols.map((s) => <option key={s.symbol} value={s.symbol}>{s.name ? `${s.name} (${s.symbol})` : s.symbol}</option>)}
              </select></label>
          )}
          <button className="ghost small" onClick={refreshJob.start} disabled={anyRunning || !apiConfigured}>{refreshJob.running ? 'Calcolo… (qualche min)' : '↻ Ricalcola prospettive'}</button>
          <button className="ghost small" onClick={calibrateJob.start} disabled={anyRunning || !apiConfigured}>{calibrateJob.running ? 'Calibro…' : '↻ Ricalibra (retrospettiva)'}</button>
          {snap?.as_of && <span className="muted small">calcolato {new Date(snap.as_of).toLocaleString()} · spot {fmtNum(spot, 2)}</span>}
        </div>
        {refreshJob.running && <p className="ok small">Ricalcolo prospettive {runningLabel(refreshJob.status)} — attendi, non serve ripremere.</p>}
        {refreshJob.status?.state === 'done' && !refreshJob.running && <p className="ok small">{doneLabel(refreshJob.status, (r) => `Prospettive ricalcolate: ${r?.ok ?? '—'} strumenti`)}</p>}
        {refreshJob.status?.state === 'error' && <p className="error">Ricalcolo prospettive non riuscito — {refreshJob.status.error}</p>}
        {calibrateJob.running && <p className="ok small">Calibrazione retrospettiva {runningLabel(calibrateJob.status)} — attendi, non serve ripremere.</p>}
        {calibrateJob.status?.state === 'done' && !calibrateJob.running && <p className="ok small">{doneLabel(calibrateJob.status, (r) => `Calibrazione aggiornata: ${r?.instruments ?? '—'} strumenti`)}</p>}
        {calibrateJob.status?.state === 'error' && <p className="error">Calibrazione non riuscita — {calibrateJob.status.error}</p>}
        {(refreshJob.err || calibrateJob.err) && <p className="error">Operazione non riuscita — {refreshJob.err || calibrateJob.err}</p>}
        {symbols.length === 0 && !anyRunning && <p className="muted small">Nessuna prospettiva ancora. Premi “Ricalcola prospettive” (usa l’API locale) — richiede qualche minuto.</p>}
        {symbols.length > 0 && !snap && <p className="muted small">Carico {symbol}…</p>}
        <ul className="tight">
          <li className="muted small">Le probabilità da <strong>opzioni</strong> sono risk-neutral (odds di mercato), non del mondo reale.</li>
          <li className="muted small"><strong>Storico condizionato</strong> = frequenza passata con n (effettivo, corretto per sovrapposizione), non garanzia.</li>
        </ul>
      </section>

      {snap && <HorizonGrid snap={snap} calBySym={calBySym} />}
      {snap && <ChosenLevel snap={snap} level={level} setLevel={setLevel} levelRet={levelRet} K={K} />}
      {snap && <Conditioning snap={snap} />}
      {cal && <CalibrationPanel cal={cal} symbol={symbol} calBySym={calBySym} />}
    </div>
  )
}

// The main view: one row per horizon with median, 68/95, effective n, source.
function HorizonGrid({ snap, calBySym }) {
  const rows = snap.horizons.map((h) => {
    const opt = snap.options?.by_horizon?.[h]
    const pair = snap.conditional?.by_horizon?.[h]?.pair
    // prefer the reliable options distribution (already in RETURNS vs proxy spot);
    // else the conditional (also returns). NEVER divide by snap.spot again.
    let src = null, median = null, p16 = null, p84 = null, p2 = null, p97 = null, n = null, srcLabel = '—', implausible = false
    if (opt?.implausible) {
      implausible = true; srcLabel = 'coerenza fallita'
    } else if (opt?.available && opt.quality?.reliable) {
      src = 'options'; srcLabel = 'opzioni'
      median = opt.median_ret; p16 = opt.p16_ret; p84 = opt.p84_ret; p2 = opt.p2_5_ret; p97 = opt.p97_5_ret
    } else if (pair?.sufficient) {
      src = 'conditional'; srcLabel = `storico (n eff. ${pair.n_effective})`
      median = pair.median; p16 = pair.p16; p84 = pair.p84; p2 = pair.p2_5; p97 = pair.p97_5; n = pair.n_effective
    }
    const covWarn = calBySym?.[h]?.verdict
    return { h, src, srcLabel, median, p16, p84, p2, p97, n, covWarn, implausible, detail: opt?.detail }
  })
  const hasData = rows.some((r) => r.src)
  return (
    <section className="panel">
      <header className="panel-head"><h2>Griglia orizzonti</h2><span className="muted small">mediana · intervallo 68% · 95% · n effettivo · fonte</span></header>
      {!hasData && <p className="honest-note">Nessuna distribuzione affidabile per questo strumento: la catena opzioni è troppo sottile (es. DAX/rame non hanno opzioni USA liquide) e lo storico condizionato è sotto soglia a questi orizzonti. Prova oro (GC=F), EUR/USD, Nasdaq, o un titolo (NVDA/MSFT): hanno catene ricche.</p>}
      {hasData && <FanChart rows={rows.filter((r) => r.src)} />}
      <div className="risk-table-wrap">
        <table className="risk-table">
          <thead><tr><th>Orizzonte</th><th>Mediana</th><th>68% (16–84)</th><th>95% (2.5–97.5)</th><th>n eff.</th><th>Fonte</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              r.implausible ? (
                <tr key={r.h} className="excluded">
                  <td>{HLABEL[r.h] || r.h}</td>
                  <td colSpan={4} className="neg">⚠ risultato implausibile — controllo di coerenza fallito{r.detail ? ` (strumento ${fmtNum(r.detail.instrument_spot, 2)}, proxy ${fmtNum(r.detail.proxy_spot, 2)}, ratio ${fmtNum(r.detail.ratio, 3)})` : ''}</td>
                  <td>coerenza fallita</td>
                </tr>
              ) : (
              <tr key={r.h} className={r.src ? '' : 'excluded'}>
                <td>{HLABEL[r.h] || r.h}</td>
                <td className={r.median == null ? 'muted' : r.median >= 0 ? 'pos' : 'neg'}>{r.median == null ? '—' : fmtPct(r.median * 100)}</td>
                <td className="muted small">{r.p16 == null ? '—' : `${fmtPct(r.p16 * 100)} … ${fmtPct(r.p84 * 100)}`}</td>
                <td className="muted small">{r.p2 == null ? '—' : `${fmtPct(r.p2 * 100)} … ${fmtPct(r.p97 * 100)}`}</td>
                <td className="muted">{r.n ?? (r.src === 'options' ? 'opz.' : '—')}</td>
                <td>{r.srcLabel}{r.covWarn && <> <InfoTip text={`Calibrazione: ${r.covWarn}`} label="calibrazione" /></>}</td>
              </tr>
              )
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small caveat">{snap.labels?.distribution} Fonte scelta per riga: opzioni se la catena è affidabile, altrimenti storico condizionato sufficiente.</p>
    </section>
  )
}

// Simple SVG fan chart: 95% (light) + 68% (dark) band + median line across horizons.
function FanChart({ rows }) {
  const W = 640, H = 200, padX = 44, padY = 16
  const xs = rows.map((_, i) => padX + (i * (W - 2 * padX)) / Math.max(rows.length - 1, 1))
  const all = rows.flatMap((r) => [r.p2, r.p97]).filter((v) => v != null)
  const lo = Math.min(...all, 0), hi = Math.max(...all, 0)
  const y = (v) => H - padY - ((v - lo) / (hi - lo || 1)) * (H - 2 * padY)
  const band = (a, b) => rows.map((r, i) => `${xs[i]},${y(r[a])}`).concat(rows.map((r, i) => `${xs[rows.length - 1 - i]},${y(r[b])}`)).join(' ')
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="fan-chart" role="img" aria-label="ventaglio distribuzioni">
      <line x1={padX} y1={y(0)} x2={W - padX} y2={y(0)} className="fan-zero" />
      <polygon points={band('p2', 'p97')} className="fan-95" />
      <polygon points={band('p16', 'p84')} className="fan-68" />
      <polyline points={rows.map((r, i) => `${xs[i]},${y(r.median)}`).join(' ')} className="fan-median" />
      {rows.map((r, i) => <text key={r.h} x={xs[i]} y={H - 2} className="fan-label">{r.h}</text>)}
      <text x={4} y={y(0)} className="fan-label">0%</text>
    </svg>
  )
}

// Chosen level: prob above/below per horizon, options vs conditional side by side.
function ChosenLevel({ snap, level, setLevel, levelRet, K }) {
  return (
    <section className="panel">
      <header className="panel-head"><h2>Livello scelto</h2><span className="muted small">prob. sopra/sotto per orizzonte · opzioni vs storico</span></header>
      <div className="desk-controls">
        <label>Il tuo livello (prezzo)<input type="number" step="any" value={level} onChange={(e) => setLevel(e.target.value)} placeholder={snap.spot ? `es. ${fmtNum(snap.spot, 0)}` : ''} /></label>
        {K != null && <span className="chip">prob. sopra {fmtNum(K, 2)}</span>}
      </div>
      {K == null ? <p className="muted small">Inserisci un livello per vedere le probabilità.</p> : (
        <div className="risk-table-wrap">
          <table className="risk-table">
            <thead><tr><th>Orizzonte</th><th>P(sopra) opzioni</th><th>P(sopra) storico</th><th>divergenza</th></tr></thead>
            <tbody>
              {snap.horizons.map((h) => {
                const opt = snap.options?.by_horizon?.[h]
                const pair = snap.conditional?.by_horizon?.[h]?.pair
                // BOTH sources are in RETURN space now. The user level (instrument
                // units) -> target return vs the instrument spot -> query bands.
                const optRet = opt?.available && opt.quality?.reliable
                  ? { median: opt.median_ret, p16: opt.p16_ret, p84: opt.p84_ret } : null
                const pOpt = optRet && levelRet != null ? aboveFromReturnBands(optRet, levelRet) : null
                const pHist = pair?.sufficient && levelRet != null ? aboveFromReturnBands(pair, levelRet) : null
                const div = pOpt != null && pHist != null ? Math.abs(pOpt - pHist) : null
                return (
                  <tr key={h}>
                    <td>{HLABEL[h] || h}</td>
                    <td>{pOpt == null ? '—' : fmtPct(pOpt * 100).replace('+', '')}</td>
                    <td>{pHist == null ? <span className="muted small">n/d</span> : fmtPct(pHist * 100).replace('+', '')}</td>
                    <td className={div != null && div > 0.15 ? 'warn' : 'muted'}>{div == null ? '—' : `${fmtPct(div * 100).replace('+', '')}`}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted small caveat">Se opzioni e storico divergono molto è informativo: il mercato prezza qualcosa che la frequenza storica non vede (o viceversa). Nessuna delle due è una previsione.</p>
    </section>
  )
}

function erf(x) {
  const t = 1 / (1 + 0.3275911 * Math.abs(x))
  const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x)
  return x >= 0 ? y : -y
}
// Conditional P(return >= levelRet), normal-approx from the median + 16/84 band.
function aboveFromReturnBands(pair, levelRet) {
  if (pair.median == null || pair.p16 == null || pair.p84 == null) return null
  const sd = (pair.p84 - pair.p16) / 2 || 1e-6
  const z = (levelRet - pair.median) / sd
  return 1 - 0.5 * (1 + erf(z / Math.SQRT2))
}

// Insufficient-sample label: show the actual effective n vs the threshold so it's
// a number ("n eff. 3 · soglia 5"), not just "campione insufficiente".
function insuffLabel(dist) {
  if (!dist) return 'campione insufficiente'
  const ne = dist.n_effective
  const y = dist.min_effective
  if (ne == null) return 'campione insufficiente'
  return `n eff. ${ne}${y != null ? ` · soglia ${y}` : ''} — insufficiente`
}
function firstSingle(single) {
  const vals = Object.values(single || {})
  return vals.length ? vals[0] : null
}

// Conditioning: pair (B) as primary, single drivers (A) alongside, with n.
function Conditioning({ snap }) {
  const c = snap.conditional
  if (!c) return null
  const regimes = c.current_regimes || {}
  return (
    <section className="panel">
      <header className="panel-head"><h2>Condizionamento</h2><span className="muted small">coppia (B) principale · singoli driver (A) accanto</span></header>
      <p className="muted small">Regimi attuali: {Object.entries(regimes).map(([d, r]) => `${d} = ${r}`).join(' · ') || 'n/d'}</p>
      <div className="risk-table-wrap">
        <table className="risk-table">
          <thead><tr><th>Orizzonte</th><th>B: coppia (mediana, n eff.)</th><th>A: singoli driver (mediana, n eff.)</th></tr></thead>
          <tbody>
            {snap.horizons.filter((h) => h !== '5a').map((h) => {
              const cell = c.by_horizon?.[h] || {}
              const pair = cell.pair
              const singles = Object.entries(cell.single || {})
              const bMissing = !pair?.sufficient
              const aVals = singles.filter(([, s]) => s?.sufficient)
              const diverge = pair?.sufficient && aVals.length && aVals.some(([, s]) => Math.abs((s.median || 0) - (pair.median || 0)) > 0.03)
              return (
                <tr key={h}>
                  <td>{HLABEL[h] || h}</td>
                  <td className={bMissing ? 'muted small' : ''}>{pair?.sufficient ? `${fmtPct(pair.median * 100)} (n ${pair.n_effective})` : insuffLabel(pair)}
                    {diverge && <span className="warn"> ⚠ diverge da A</span>}</td>
                  <td className="muted small">{aVals.length ? aVals.map(([d, s]) => `${d}: ${fmtPct(s.median * 100)} (n ${s.n_effective})`).join(' · ') : insuffLabel(firstSingle(cell.single))}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="muted small caveat">Se B ha n basso o diverge molto da A, fidati meno della coppia: poche osservazioni indipendenti. {snap.labels?.conditional}</p>
    </section>
  )
}

function CalibrationPanel({ cal, symbol, calBySym }) {
  return (
    <section className="panel">
      <header className="panel-head"><h2>Calibrazione (retrospettiva)</h2><span className="muted small">il 68% contiene davvero il 68%? · {cal.calibrated_at ? new Date(cal.calibrated_at).toLocaleDateString() : ''}</span></header>
      {!calBySym ? <p className="muted small">Nessuna calibrazione per {symbol}. Premi “Ricalibra (retrospettiva)”.</p> : (
        <div className="risk-table-wrap">
          <table className="risk-table">
            <thead><tr><th>Orizzonte</th><th>Coverage 68%</th><th>Coverage 95%</th><th>n</th><th>Verdetto / correzione</th></tr></thead>
            <tbody>
              {Object.entries(calBySym).map(([h, m]) => (
                <tr key={h}>
                  <td>{HLABEL[h] || h}</td>
                  <td className={cov(m.coverage_68, 0.68)}>{m.coverage_68 == null ? '—' : fmtPct(m.coverage_68 * 100).replace('+', '')}</td>
                  <td className={cov(m.coverage_95, 0.95)}>{m.coverage_95 == null ? '—' : fmtPct(m.coverage_95 * 100).replace('+', '')}</td>
                  <td className="muted">{m.n ?? '—'}</td>
                  <td className="muted small">{m.verdict || (m.recalibration?.applied ? `corretta: dispersione ×${fmtNum(m.recalibration.scale, 2)}` : 'ok / nessuna correzione')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted small caveat">{cal.note} La correzione tocca SOLO la dispersione (larghezza), mai la direzione, e solo se migliora fuori campione.</p>
    </section>
  )
}
function cov(v, target) { if (v == null) return 'muted'; return Math.abs(v - target) <= 0.08 ? 'pos' : 'warn' }

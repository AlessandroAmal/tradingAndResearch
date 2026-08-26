import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchCalibration, fetchDecisionBoards } from '../api/data'
import { recalibrate, getCalibrateStatus, apiConfigured } from '../api/control'
import { useJobStatus, runningLabel, doneLabel } from '../lib/useJobStatus'
import { fmtNum } from '../lib/format'

const HORIZONS = [1, 3, 5, 10, 15, 21]
const FACTOR_LABEL = { rsi: 'RSI', streak: 'Streak', trend_ma: 'Trend vs MA', ma200_dist: 'Distanza MA200' }
const MACRO_LABEL = {
  DFII10: 'Tasso reale 10y', T10YIE: 'Breakeven inflazione', DTWEXBGS: 'Dollaro (broad)',
  '^VIX': 'VIX', GFDEGDQ188S: 'Debito/PIL', A091RC1Q027SBEA: 'Interessi sul debito',
  FYFSD: 'Deficit federale', FED_ECB_SPREAD: 'Spread Fed-BCE', DGS2: 'Tasso 2y USA',
  BAMLH0A0HYM2: 'Spread High Yield',
}
// Human label for any factor key, including macro:<FRED_ID> drivers.
function labelFactor(name) {
  if (FACTOR_LABEL[name]) return FACTOR_LABEL[name]
  if (name.startsWith('macro:')) {
    const id = name.slice(6)
    return MACRO_LABEL[id] || id
  }
  return name
}
// A factor×horizon is a SURVIVOR when the calibration marked it significant
// (block-bootstrap CI excludes 0, effective n≥30, AND passes the FDR correction).
// Adjacent horizons for the same factor×instrument are GROUPED into one row with a
// horizon range, so a factor surviving at 5/10/15g is one story, not three.
function collectSurvivors(results) {
  const groups = []
  for (const [symbol, factors] of Object.entries(results || {})) {
    for (const [name, byH] of Object.entries(factors || {})) {
      if (!byH || byH.non_testable) continue
      // horizons (in canonical order) where this factor×instrument survived
      const hits = HORIZONS.map((h, i) => ({ h, i, st: byH[String(h)] }))
        .filter((x) => x.st && x.st.significant && x.st.ic != null)
      if (!hits.length) continue
      // split into runs of ADJACENT horizons (consecutive indices in HORIZONS)
      let run = [hits[0]]
      const runs = []
      for (let k = 1; k < hits.length; k++) {
        if (hits[k].i === run[run.length - 1].i + 1) run.push(hits[k])
        else { runs.push(run); run = [hits[k]] }
      }
      runs.push(run)
      for (const r of runs) {
        const ics = r.map((x) => x.st.ic)
        const peak = ics.reduce((a, b) => (Math.abs(b) > Math.abs(a) ? b : a))
        groups.push({
          symbol, name,
          hFrom: r[0].h, hTo: r[r.length - 1].h, span: r.length,
          icMin: Math.min(...ics), icMax: Math.max(...ics), peak,
          nEff: Math.min(...r.map((x) => x.st.n_effective ?? 0)),
          anomalous: r.some((x) => x.st.anomalous_sign),
          shortWindow: r.some((x) => x.st.short_window),
        })
      }
    }
  }
  return groups.sort((a, b) => Math.abs(b.peak) - Math.abs(a.peak))
}
function horizonRange(g) {
  return g.hFrom === g.hTo ? `${g.hFrom}g` : `${g.hFrom}–${g.hTo}g`
}
// Macro coverage (period + years + short-window) is duplicated across horizons;
// read it off any cell that carries it. Returns null for non-macro factors.
function macroCoverage(byH) {
  for (const h of HORIZONS) {
    const st = byH[String(h)]
    if (st && st.covered_years != null) return st
  }
  return null
}
function icRange(g) {
  return g.icMin === g.icMax ? fmtNum(g.peak, 3) : `${fmtNum(g.icMin, 3)}…${fmtNum(g.icMax, 3)}`
}

// CALIBRAZIONE INDICATORI — does each factor actually predict? MEASURED, no
// look-ahead, deflation-aware. Most factors ~0 IC: that is the ATTESO result.
export default function Calibration() {
  const [cal, setCal] = useState(null)
  const [symbols, setSymbols] = useState([])
  const [sel, setSel] = useState('')

  const load = useCallback(() => {
    fetchCalibration().then(({ data }) => {
      setCal(data || null)
      const syms = data?.results ? Object.keys(data.results) : []
      setSel((s) => s || syms[0] || '')
    })
    fetchDecisionBoards().then(({ data }) => setSymbols((data || []).map((r) => r.symbol)))
  }, [])
  useEffect(() => { load() }, [load])

  const { status, err, start, running } = useJobStatus(getCalibrateStatus, recalibrate, load)

  const factors = useMemo(() => (cal?.results?.[sel]) || {}, [cal, sel])
  const testable = Object.entries(factors).filter(([, v]) => !v.non_testable)
  const nonTestable = Object.entries(factors).filter(([, v]) => v.non_testable)
  const weights = cal?.weights?.[sel] || {}
  const survivors = useMemo(() => collectSurvivors(cal?.results), [cal])

  return (
    <div className="desk">
      <section className="panel">
        <header className="panel-head">
          <h2>Calibrazione indicatori</h2>
          <span className="muted small">quali fattori predicono DAVVERO · misurato, senza look-ahead</span>
        </header>

        <div className="desk-controls">
          <button className="primary" onClick={start} disabled={running || !apiConfigured}>{running ? 'Ricalibro…' : '↻ Ricalibra lancetta da evidenza'}</button>
          {cal?.calibrated_at && <span className="muted small">ultima: {new Date(cal.calibrated_at).toLocaleString()} · periodo {cal.period_start}…{cal.period_end} · {cal.test_count} test</span>}
          {!apiConfigured && <span className="muted small">Configura l’API locale per ricalibrare.</span>}
        </div>
        {running && <p className="ok small">Ricalibrazione {runningLabel(status)} — attendi, non serve ripremere.</p>}
        {status?.state === 'done' && !running && <p className="ok small">{doneLabel(status, (r) => `Ricalibrazione completata: ${r?.instruments ?? '—'} strumenti, ${r?.test_count ?? '—'} test`)}</p>}
        {status?.state === 'error' && <p className="error">Ricalibrazione non riuscita — {status.error}</p>}
        {err && <p className="error">Ricalibrazione non riuscita — {err}</p>}
        {!cal && !running && status?.state !== 'done' && <p className="muted small">Nessuna calibrazione ancora. Premi “Ricalibra” (usa l’API locale).</p>}

        <p className="honest-note">La maggior parte dei fattori avrà valore <strong>~zero</strong>: è il risultato ATTESO e informativo, non un fallimento. «Significativo su {cal?.test_count || 'N'} test» ≠ vero: stiamo testando decine di combinazioni (deflazione).</p>
      </section>

      {cal && (
        <section className="panel">
          <header className="panel-head">
            <h2>Cosa è sopravvissuto <span className="pos">({survivors.length})</span></h2>
            <span className="muted small">fattori significativi post-deflazione su {cal.test_count} test · l’output principale del run</span>
          </header>
          {survivors.length === 0 ? (
            <p className="honest-note">Nessun fattore ha superato la deflazione: su {cal.test_count} test, nessun IC resta significativo dopo block-bootstrap (n effettivo) e correzione FDR. <strong>È un esito legittimo e informativo</strong> — la maggior parte degli indicatori non predice a questi orizzonti.</p>
          ) : (
            <>
              <div className="risk-table-wrap">
                <table className="risk-table">
                  <thead><tr><th>Strumento</th><th>Fattore</th><th>Orizzonti</th><th>IC</th><th>n eff.</th><th>Nota</th></tr></thead>
                  <tbody>
                    {survivors.map((s, i) => (
                      <tr key={i} className={s.anomalous ? 'excluded' : 'survivor-row'}>
                        <td><button className="linklike" onClick={() => setSel(s.symbol)}>{s.symbol}</button></td>
                        <td>{labelFactor(s.name)}</td>
                        <td className="muted small">{horizonRange(s)}{s.span > 1 ? ` (${s.span})` : ''}</td>
                        <td className={s.peak > 0 ? 'pos' : 'neg'}><strong>{icRange(s)}</strong>{s.peak > 0 ? ' ↑' : ' ↓'}</td>
                        <td className="muted">{s.nEff || '—'}</td>
                        <td className="muted small">
                          {s.anomalous && <span className="neg">⚠ segno anomalo — escluso dai pesi</span>}
                          {!s.anomalous && s.shortWindow && <span className="warn">⚠ finestra breve (&lt;3 anni)</span>}
                          {!s.anomalous && !s.shortWindow && <span className="pos">edge candidato</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="muted small caveat">IC positivo = il fattore alto anticipa rendimenti futuri più alti; negativo = più bassi. «n eff.» = osservazioni indipendenti (≈ n/orizzonte, per le finestre sovrapposte). Significatività = CI block-bootstrap esclude 0 <strong>e</strong> supera la correzione FDR (Benjamini-Hochberg) su {cal.test_count} test. <strong>⚠ segno anomalo</strong> = IC significativo ma di segno contrario all'atteso economico → azzerato, non invertito, NON entra nei pesi/tilt. Un IC significativo NON è una previsione.</p>
            </>
          )}
        </section>
      )}

      {cal && (
        <section className="panel">
          <header className="panel-head">
            <h2>IC per fattore × orizzonte — heatmap</h2>
            <label className="muted small">Strumento
              <select value={sel} onChange={(e) => setSel(e.target.value)}>
                {Object.keys(cal.results || {}).map((s) => <option key={s} value={s}>{s}</option>)}
              </select></label>
          </header>
          <div className="risk-table-wrap">
            <table className="risk-table heatmap">
              <thead><tr><th>Fattore</th>{HORIZONS.map((h) => <th key={h}>{h}g</th>)}</tr></thead>
              <tbody>
                {testable.map(([name, byH]) => {
                  const cov = macroCoverage(byH)
                  return (
                  <tr key={name}>
                    <td>{labelFactor(name)}
                      {cov && <><br /><span className={`muted small ${cov.short_window ? 'warn' : ''}`} title={cov.short_window ? 'finestra breve: un solo regime macro — alto rischio artefatto' : ''}>{cov.covered_from?.slice(0, 4)}–{cov.covered_to?.slice(0, 4)} · {cov.covered_years}a{cov.short_window ? ' ⚠' : ''}</span></>}
                    </td>
                    {HORIZONS.map((h) => {
                      const st = byH[String(h)] || {}
                      const anom = st.significant && st.anomalous_sign
                      return <td key={h} className={cell(st)} title={`IC=${st.ic == null ? 'n/d' : fmtNum(st.ic, 3)} · n=${st.n ?? '—'} · n eff.=${st.n_effective ?? '—'}${st.significant ? (anom ? ' · SOPRAVVISSUTO ma SEGNO ANOMALO' : ' · SOPRAVVISSUTO (CI + FDR)') : ''}`}>
                        {st.significant && <span className={`survivor-badge ${anom ? 'neg' : ''}`}>{anom ? '⚠' : '✓'}</span>}
                        {st.ic == null ? '—' : fmtNum(st.ic, 2)}<br /><span className="muted small">n{st.n ?? '—'}·e{st.n_effective ?? '—'}</span>
                      </td>
                    })}
                  </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="muted small caveat">IC = correlazione di rango fattore→rendimento futuro. <span className="survivor-badge">✓</span> = SOPRAVVISSUTO (CI block-bootstrap esclude 0, n eff.≥30, e supera FDR); <span className="survivor-badge neg">⚠</span> = sopravvissuto ma segno anomalo. «n·e» = n grezzo · n effettivo (≈ n/orizzonte, per finestre sovrapposte). Sotto la riga macro: periodo coperto e anni (⚠ = finestra breve &lt;3 anni, alto rischio artefatto di regime).</p>

          <h3 className="ctx-h muted small">Non testabili con i dati disponibili</h3>
          <ul className="tight">{nonTestable.map(([name, v]) => <li key={name} className="muted small">{labelFactor(name)}: {v.reason}</li>)}</ul>

          <h3 className="ctx-h muted small">Pesi della lancetta (da evidenza{cal.weight_horizon ? `, orizzonte ${cal.weight_horizon}g` : ''})</h3>
          {Object.keys(weights).length === 0 ? <p className="muted small">Nessun fattore significativo per {sel}: la lancetta resta a pesi di config (contesto).</p> : (
            <ul className="tight">
              {Object.entries(weights).map(([k, w]) => (
                <li key={k}>{labelFactor(k)}: peso <strong>{fmtNum(w.weight, 3)}</strong>{w.contrary ? <span className="neg"> · CONTRARIO (azzerato, non invertito)</span> : w.weight > 0 ? <span className="pos"> · significativo</span> : <span className="muted small"> · nessun valore predittivo misurato</span>}</li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  )
}

function cell(st) {
  if (st.ic == null) return 'muted'
  if (!st.significant) return ''
  return st.ic > 0 ? 'pos' : 'neg'
}

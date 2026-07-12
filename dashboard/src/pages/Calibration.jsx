import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchCalibration, fetchDecisionBoards } from '../api/data'
import { recalibrate, apiConfigured } from '../api/control'
import { fmtNum } from '../lib/format'

const HORIZONS = [1, 3, 5, 10, 15, 21]
const FACTOR_LABEL = { rsi: 'RSI', streak: 'Streak', trend_ma: 'Trend vs MA', ma200_dist: 'Distanza MA200' }

// CALIBRAZIONE INDICATORI — does each factor actually predict? MEASURED, no
// look-ahead, deflation-aware. Most factors ~0 IC: that is the ATTESO result.
export default function Calibration() {
  const [cal, setCal] = useState(null)
  const [symbols, setSymbols] = useState([])
  const [sel, setSel] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  const load = useCallback(() => {
    fetchCalibration().then(({ data }) => {
      setCal(data || null)
      const syms = data?.results ? Object.keys(data.results) : []
      setSel((s) => s || syms[0] || '')
    })
    fetchDecisionBoards().then(({ data }) => setSymbols((data || []).map((r) => r.symbol)))
  }, [])
  useEffect(() => { load() }, [load])

  const run = useCallback(async () => {
    setBusy(true); setErr(null)
    const { error } = await recalibrate()
    setBusy(false)
    if (error) { setErr(error.message); return }
    load()
  }, [load])

  const factors = useMemo(() => (cal?.results?.[sel]) || {}, [cal, sel])
  const testable = Object.entries(factors).filter(([, v]) => !v.non_testable)
  const nonTestable = Object.entries(factors).filter(([, v]) => v.non_testable)
  const weights = cal?.weights?.[sel] || {}

  return (
    <div className="desk">
      <section className="panel">
        <header className="panel-head">
          <h2>Calibrazione indicatori</h2>
          <span className="muted small">quali fattori predicono DAVVERO · misurato, senza look-ahead</span>
        </header>

        <div className="desk-controls">
          <button className="primary" onClick={run} disabled={busy || !apiConfigured}>{busy ? 'Ricalibro…' : '↻ Ricalibra lancetta da evidenza'}</button>
          {cal?.calibrated_at && <span className="muted small">ultima: {new Date(cal.calibrated_at).toLocaleString()} · periodo {cal.period_start}…{cal.period_end} · {cal.test_count} test</span>}
          {!apiConfigured && <span className="muted small">Configura l’API locale per ricalibrare.</span>}
        </div>
        {err && <p className="error">Ricalibrazione non riuscita — {err}</p>}
        {!cal && <p className="muted small">Nessuna calibrazione ancora. Premi “Ricalibra” (usa l’API locale).</p>}

        <p className="honest-note">La maggior parte dei fattori avrà valore <strong>~zero</strong>: è il risultato ATTESO e informativo, non un fallimento. «Significativo su {cal?.test_count || 'N'} test» ≠ vero: stiamo testando decine di combinazioni (deflazione).</p>
      </section>

      {cal && (
        <section className="panel">
          <header className="panel-head">
            <h2>IC per fattore × orizzonte</h2>
            <label className="muted small">Strumento
              <select value={sel} onChange={(e) => setSel(e.target.value)}>
                {Object.keys(cal.results || {}).map((s) => <option key={s} value={s}>{s}</option>)}
              </select></label>
          </header>
          <div className="risk-table-wrap">
            <table className="risk-table">
              <thead><tr><th>Fattore</th>{HORIZONS.map((h) => <th key={h}>{h}g</th>)}</tr></thead>
              <tbody>
                {testable.map(([name, byH]) => (
                  <tr key={name}>
                    <td>{FACTOR_LABEL[name] || name}</td>
                    {HORIZONS.map((h) => {
                      const st = byH[String(h)] || {}
                      return <td key={h} className={cell(st)} title={`n=${st.n ?? '—'}${st.significant ? ' · significativo' : ''}`}>
                        {st.ic == null ? '—' : fmtNum(st.ic, 2)}{st.significant ? '*' : ''}<br /><span className="muted small">n={st.n ?? '—'}</span>
                      </td>
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted small caveat">IC = correlazione di rango fattore→rendimento futuro. * = CI bootstrap esclude 0 e n≥30. n sempre visibile; sotto soglia = campione insufficiente, non una probabilità.</p>

          <h3 className="ctx-h muted small">Non testabili con i dati disponibili</h3>
          <ul className="tight">{nonTestable.map(([name, v]) => <li key={name} className="muted small">{FACTOR_LABEL[name] || name}: {v.reason}</li>)}</ul>

          <h3 className="ctx-h muted small">Pesi della lancetta (da evidenza, orizzonte {cal.weight_horizon}g)</h3>
          {Object.keys(weights).length === 0 ? <p className="muted small">Nessun fattore significativo per {sel}: la lancetta resta a pesi di config (contesto).</p> : (
            <ul className="tight">
              {Object.entries(weights).map(([k, w]) => (
                <li key={k}>{FACTOR_LABEL[k] || k}: peso <strong>{fmtNum(w.weight, 3)}</strong>{w.contrary ? <span className="neg"> · CONTRARIO (azzerato, non invertito)</span> : w.weight > 0 ? <span className="pos"> · significativo</span> : <span className="muted small"> · nessun valore predittivo misurato</span>}</li>
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

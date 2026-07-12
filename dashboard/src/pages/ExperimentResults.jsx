import { useEffect, useMemo, useState } from 'react'
import { fetchExperimentPositions } from '../api/data'
import { aggregate, DELAY_LABEL, SURPRISE_LABEL } from '../lib/experiment'
import { fmtNum, fmtPct, relativeTime } from '../lib/format'

const MIN_SAMPLE = 20

// Controlled macro-event experiment — RESULTS. Aggregates CLOSED paper positions
// (opened automatically at t+5m/30m/2h/1d after US data, both directions) into
// evidence. READ-ONLY, never a signal: n is always shown; below threshold is a
// sample, not a probability.
export default function ExperimentResults({ refreshKey = 0, nowMs = Date.now() }) {
  const [rows, setRows] = useState([])
  const [error, setError] = useState(null)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    fetchExperimentPositions().then(({ data, error }) => {
      if (error) setError(error.message)
      setRows(data || [])
      setLoaded(true)
    })
  }, [refreshKey])

  const open = useMemo(() => rows.filter((p) => p.status === 'open'), [rows])
  const closed = useMemo(() => rows.filter((p) => p.status === 'closed'), [rows])
  const byDelay = useMemo(() => aggregate(rows, ['symbol', 'delay_min', 'horizon'], { minSample: MIN_SAMPLE }), [rows])
  const bySurprise = useMemo(() => aggregate(rows, ['symbol', 'surprise_dir', 'horizon'], { minSample: MIN_SAMPLE }), [rows])

  return (
    <div className="desk">
      <section className="panel">
        <header className="panel-head">
          <h2>Esperimento eventi — risultati</h2>
          <span className="muted small">misura cosa succede dopo i dati USA · paper, mai un ordine</span>
        </header>

        <p className="honest-note">
          <strong>Misura, non un segnale.</strong> Il tool apre posizioni di TEST (paper) a vari ritardi dopo i dati
          macro USA, in entrambe le direzioni, per raccogliere evidenza. Nessuna di queste diventa una regola
          operativa finché non c’è un campione robusto. Un evento non è un campione: servono decine di osservazioni
          prima di dire qualcosa.
        </p>
        <ul className="tight">
          <li className="muted small">n sempre visibile; sotto soglia (n&lt;{MIN_SAMPLE}) = <strong>campione insufficiente</strong>, NON una probabilità.</li>
          <li className="muted small">i primi minuti hanno spread larghi e slippage: i risultati a <strong>t+5min</strong> sono ottimistici se non modellati.</li>
          <li className="muted small">separato dal rischio reale e dalle tue paper manuali: non inquina heat né la review del tuo processo.</li>
        </ul>

        {error && <p className="error small">Esperimenti non disponibili — {error}</p>}
        {loaded && rows.length === 0 && !error && (
          <p className="muted small">Nessun esperimento ancora. Le posizioni si aprono automaticamente dopo il prossimo dato USA (CPI/NFP/FOMC…).</p>
        )}

        <div className="stat-grid">
          <Stat label="Aperti (in corso)" value={open.length} />
          <Stat label="Chiusi (misurati)" value={closed.length} />
          <Stat label="Ultimo aperto" value={rows[0]?.opened_at ? relativeTime(rows[0].opened_at, nowMs) : '—'} />
        </div>
      </section>

      <ResultTable
        title="Per ritardo d'ingresso (entrare subito vs aspettare)"
        rows={byDelay}
        cols={['symbol', 'delay_min', 'horizon']}
        fmtGroup={(g) => `${g.symbol} · ${DELAY_LABEL[g.delay_min] || `t+${g.delay_min}m`} · ${g.horizon}`}
      />
      <ResultTable
        title="Per direzione della sorpresa"
        rows={bySurprise}
        cols={['symbol', 'surprise_dir', 'horizon']}
        fmtGroup={(g) => `${g.symbol} · ${SURPRISE_LABEL[g.surprise_dir] || g.surprise_dir || 'sorpresa n/d'} · ${g.horizon}`}
      />
    </div>
  )
}

function ResultTable({ title, rows, fmtGroup }) {
  return (
    <section className="panel">
      <header className="panel-head"><h2>{title}</h2></header>
      {rows.length === 0 ? (
        <p className="muted small">Nessun esperimento chiuso ancora in questo raggruppamento.</p>
      ) : (
        <div className="risk-table-wrap">
          <table className="risk-table">
            <thead><tr>
              <th>Gruppo</th><th>n</th><th>% positivi</th><th>rend. medio</th><th>mediana</th><th>disp. (σ)</th>
            </tr></thead>
            <tbody>
              {rows.map((c, i) => (
                <tr key={i} className={c.sufficient ? '' : 'excluded'}>
                  <td>{fmtGroup(c.group)}</td>
                  <td className={c.sufficient ? '' : 'warn'}>{c.n}{c.sufficient ? '' : ' (insuff.)'}</td>
                  <td>{fmtPct(c.pctPositive * 100).replace('+', '')}</td>
                  <td className={signCls(c.meanReturn)}>{fmtPct(c.meanReturn * 100)}</td>
                  <td className="muted">{fmtPct(c.medianReturn * 100)}</td>
                  <td className="muted">{c.stdev == null ? '—' : fmtPct(c.stdev * 100).replace('+', '')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted small caveat">Righe attenuate = campione insufficiente (n&lt;{MIN_SAMPLE}): nessuna conclusione. Misura, non un segnale.</p>
    </section>
  )
}

function Stat({ label, value }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
    </div>
  )
}
function signCls(v) { return v == null ? '' : v > 0 ? 'pos' : v < 0 ? 'neg' : '' }

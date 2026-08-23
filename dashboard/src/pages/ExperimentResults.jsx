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
  // Measure the PRICE MOVE: use only the long leg (short is its exact mirror, so
  // mixing them averages to zero and hides the result).
  const longClosed = useMemo(() => rows.filter((p) => p.side === 'long'), [rows])
  const byDelay = useMemo(() => aggregate(longClosed, ['symbol', 'delay_min', 'horizon'], { minSample: MIN_SAMPLE }), [longClosed])
  const bySurprise = useMemo(() => aggregate(longClosed, ['symbol', 'surprise_dir', 'horizon'], { minSample: MIN_SAMPLE }), [longClosed])
  const events = useMemo(() => new Set(closed.map((p) => `${p.entry_conditions?.event}|${p.entry_conditions?.event_time}`)).size, [closed])

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
          <Stat label="Eventi misurati" value={events} />
          <Stat label="Aperti (in corso)" value={open.length} />
          <Stat label="Chiusi (misurati)" value={closed.length} />
          <Stat label="Ultimo aperto" value={rows[0]?.opened_at ? relativeTime(rows[0].opened_at, nowMs) : '—'} />
        </div>
      </section>

      <Conclusioni events={events} closed={closed.length} byDelay={byDelay} />

      {open.length > 0 && <OpenExperiments open={open} nowMs={nowMs} />}

      <ResultTable
        title="Movimento del prezzo per ritardo d'ingresso (entrare subito vs aspettare)"
        rows={byDelay}
        fmtGroup={(g) => `${g.symbol} · ${DELAY_LABEL[g.delay_min] || `t+${g.delay_min}m`} · ${g.horizon}`}
      />
      <ResultTable
        title="Movimento del prezzo per direzione della sorpresa"
        rows={bySurprise}
        fmtGroup={(g) => `${g.symbol} · ${SURPRISE_LABEL[g.surprise_dir] || g.surprise_dir || 'sorpresa n/d'} · ${g.horizon}`}
      />
    </div>
  )
}

// Honest read-out: what we can/can't say yet. With 1 event, nothing.
function Conclusioni({ events, closed, byDelay }) {
  const sufficient = byDelay.filter((c) => c.sufficient)
  const moves = byDelay.filter((c) => c.n > 0)
  const best = moves.reduce((a, b) => (b.meanReturn > (a?.meanReturn ?? -Infinity) ? b : a), null)
  const worst = moves.reduce((a, b) => (b.meanReturn < (a?.meanReturn ?? Infinity) ? b : a), null)
  return (
    <section className="panel">
      <header className="panel-head"><h2>Conclusioni</h2><span className="muted small">cosa possiamo dire (per ora: quasi nulla)</span></header>
      <p className="honest-note">
        <strong>{events} evento{events === 1 ? '' : 'i'} misurato{events === 1 ? '' : 'i'}, {closed} posizioni chiuse.</strong>{' '}
        {sufficient.length === 0
          ? `Nessuna combinazione raggiunge la soglia (n≥${MIN_SAMPLE}): NESSUNA conclusione operativa. Un evento non è un campione — servono decine di CPI/NFP prima di dire qualcosa.`
          : `${sufficient.length} combinazioni sopra soglia: leggile con cautela (deflazione).`}
      </p>
      {moves.length > 0 && (
        <p className="muted small">
          Finora (DATO osservato, non un segnale): movimento medio più ampio al rialzo su{' '}
          <strong>{best ? `${best.group.symbol} ${DELAY_LABEL[best.group.delay_min] || ''} ${best.group.horizon} (${fmtPct(best.meanReturn * 100)})` : '—'}</strong>,
          più al ribasso su <strong>{worst ? `${worst.group.symbol} ${DELAY_LABEL[worst.group.delay_min] || ''} ${worst.group.horizon} (${fmtPct(worst.meanReturn * 100)})` : '—'}</strong>.
          Con n piccolo è rumore.
        </p>
      )}
      <p className="muted small caveat">«Movimento» = return della posizione LONG (lo short è l’esatto opposto). Alcuni 0% = feed prezzi non aggiornato in quella finestra. Misura, non un segnale: nessuna diventa una regola finché il campione non è robusto.</p>
    </section>
  )
}

// The individual open experiment positions — WHICH ones are running now.
function OpenExperiments({ open, nowMs }) {
  const byEvent = useMemo(() => {
    const m = {}
    for (const p of open) {
      const c = p.entry_conditions || {}
      const key = `${c.event || '—'} · ${String(c.event_time || '').slice(0, 16)}`
      ;(m[key] = m[key] || []).push(p)
    }
    // sort each group by delay then horizon
    for (const k of Object.keys(m)) m[k].sort((a, b) => (a.entry_conditions?.delay_min - b.entry_conditions?.delay_min) || 0)
    return m
  }, [open])

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Aperti in corso ({open.length})</h2>
        <span className="muted small">le posizioni di TEST generate dopo l’ultimo dato · si chiudono da sole all’orizzonte</span>
      </header>
      {Object.entries(byEvent).map(([ev, list]) => (
        <details key={ev} className="factors" open={Object.keys(byEvent).length <= 2}>
          <summary>{ev} — {list.length} posizioni</summary>
          <div className="risk-table-wrap">
            <table className="risk-table">
              <thead><tr><th>Strumento</th><th>Dir.</th><th>Ritardo</th><th>Orizzonte</th><th>Entry</th><th>Sorpresa</th><th>Aperta</th><th>Chiude tra</th></tr></thead>
              <tbody>
                {list.map((p) => {
                  const c = p.entry_conditions || {}
                  return (
                    <tr key={p.id}>
                      <td className="sym">{p.symbol}</td>
                      <td><span className={`badge ${p.side}`}>{p.side}</span></td>
                      <td>{DELAY_LABEL[c.delay_min] || `t+${c.delay_min}m`}</td>
                      <td>{c.horizon}</td>
                      <td>{c.entry_price == null ? '—' : fmtNum(c.entry_price, 2)}</td>
                      <td className="muted small">{SURPRISE_LABEL[c.surprise?.direction] || (c.surprise?.available === false ? 'consenso n/d' : '—')}</td>
                      <td className="muted small">{p.opened_at ? relativeTime(p.opened_at, nowMs) : '—'}</td>
                      <td className="muted small">{c.exit_time ? countdownTo(c.exit_time, nowMs) : '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </details>
      ))}
      <p className="muted small caveat">Ogni cella (strumento × ritardo × orizzonte × direzione) è una posizione paper distinta: 3 strumenti × 4 ritardi × 3 orizzonti × 2 direzioni = 72 per evento. Misura, non un segnale; mai un ordine.</p>
    </section>
  )
}

function countdownTo(iso, nowMs) {
  const ms = new Date(iso).getTime() - nowMs
  if (Number.isNaN(ms)) return '—'
  if (ms <= 0) return 'a breve'
  const h = Math.floor(ms / 3_600_000)
  if (h < 48) return `${h}h`
  return `${Math.floor(h / 24)}g`
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
              <th>Gruppo</th><th>n</th><th>% salito</th><th>mov. medio</th><th>mediana</th><th>disp. (σ)</th>
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

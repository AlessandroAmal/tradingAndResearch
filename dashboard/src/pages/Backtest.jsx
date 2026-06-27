import { useEffect, useMemo, useState } from 'react'
import { fetchBacktestRuns, fetchBacktestRun } from '../api/data'
import { fmtNum, fmtPct, relativeTime } from '../lib/format'
import InfoTip from '../components/InfoTip'
import { BACKTEST_HELP_BY_KEY as BH } from '../data/guide'

// Research / Backtest bench (read-only). Runs are produced by the worker CLI
// (`python -m app.main backtest …`) and read here. Built to make overfitting
// VISIBLE: NET results, out-of-sample first, deflated Sharpe, honest caveats.
export default function Backtest() {
  const [runs, setRuns] = useState([])
  const [id, setId] = useState('')
  const [run, setRun] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchBacktestRuns().then(({ data, error }) => {
      if (error) { setError(error.message); return }
      setRuns(data || [])
      if (data?.length) setId(data[0].id)
    })
  }, [])

  useEffect(() => {
    if (!id) return
    fetchBacktestRun(id).then(({ data, error }) => {
      if (error) { setError(error.message); return }
      setRun(data || null)
    })
  }, [id])

  const result = run?.result || null

  return (
    <div className="desk">
      <section className="panel">
        <header className="panel-head">
          <h2>Ricerca / Backtest</h2>
          <span className="muted small">misura l’edge · non genera segnali · passato ≠ futuro</span>
        </header>

        {error && <p className="error">Backtest non disponibile — {error}</p>}
        {runs.length === 0 && !error && (
          <p className="muted small">
            Nessun run. Esegui dal worker: <code>python -m app.main backtest --rule streak_reversion --instrument GC=F</code>
            {' '}oppure <code>python -m app.main backtest --scan</code>.
          </p>
        )}

        {runs.length > 0 && (
          <div className="desk-controls">
            <label>Run
              <select value={id} onChange={(e) => setId(e.target.value)}>
                {runs.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.kind === 'scan' ? `SCAN · ${r.rule || 'multi'}` : `${r.rule} · ${r.instrument}`}
                    {' · '}{new Date(r.created_at).toLocaleDateString()}
                  </option>
                ))}
              </select>
            </label>
            {run?.created_at && <span className="muted small">calcolato {relativeTime(run.created_at)}</span>}
          </div>
        )}
      </section>

      {result?.kind === 'single' && <SingleView r={result} />}
      {result?.kind === 'scan' && <ScanView r={result} />}
      {result && <Caveats items={result.caveats} />}
    </div>
  )
}

// --- single run ------------------------------------------------------
function SingleView({ r }) {
  const oosNet = r.metrics.out_of_sample.net
  const oosBh = r.metrics.out_of_sample.bh_net
  const fullNet = r.metrics.full.net
  const deg = r.degradation.sharpe
  const boot = r.bootstrap

  return (
    <>
      <section className="panel">
        <header className="panel-head">
          <h2>Out-of-sample · NET <InfoTip text={BH.oos.text} label={BH.oos.label} /></h2>
          <span className="muted small">{r.rule} su {r.instrument} · costi {r.cost_bps} bps/lato · il dato che conta</span>
        </header>
        <div className="stat-grid">
          <Stat label="Rend. totale" value={fmtPct(oosNet.total_return * 100)} cls={signClass(oosNet.total_return)} />
          <Stat label="vs Buy&Hold" tip={BH.delta_bh} value={fmtPct(r.delta_vs_bh_net.out_of_sample * 100)} cls={signClass(r.delta_vs_bh_net.out_of_sample)} />
          <Stat label="CAGR" value={oosNet.cagr == null ? '—' : fmtPct(oosNet.cagr * 100)} />
          <Stat label="Sharpe" tip={BH.sharpe} value={fmtNum(oosNet.sharpe, 2)} />
          <Stat label="Sortino" value={fmtNum(oosNet.sortino, 2)} />
          <Stat label="Max DD" value={fmtPct(oosNet.max_drawdown * 100)} cls="neg" />
          <Stat label="Win rate" value={oosNet.win_rate == null ? '—' : fmtPct(oosNet.win_rate * 100)} />
          <Stat label="N° trade" value={fmtNum(oosNet.n_trades, 0)} />
          <Stat label="% in mercato" value={fmtPct(oosNet.time_in_market * 100)} />
          <Stat label="B&H netto (OOS)" value={fmtPct(oosBh.total_return * 100)} />
        </div>
        <p className="muted small">
          Confronto onesto: la strategia ha reso {fmtPct(oosNet.total_return * 100)} netto out-of-sample
          contro {fmtPct(oosBh.total_return * 100)} del semplice buy-and-hold sullo stesso strumento.
        </p>
      </section>

      <section className="panel">
        <header className="panel-head">
          <h2>Degrado in-sample → out-of-sample <InfoTip text={BH.degradation.text} label={BH.degradation.label} /></h2>
          <span className="muted small">il segnale chiave di overfitting</span>
        </header>
        <div className={`divergence diverg-${degClass(deg.retained_pct)}`}>
          <span className="diverg-tag">Sharpe</span>
          <span>
            in-sample <strong>{fmtNum(deg.in_sample, 2)}</strong> → out-of-sample <strong>{fmtNum(deg.out_of_sample, 2)}</strong>
            {deg.retained_pct != null && <> · trattenuto <strong>{fmtNum(deg.retained_pct, 0)}%</strong></>}
          </span>
        </div>
        <p className="muted small">
          Un forte calo dall’in-sample all’out-of-sample = la regola era adattata al passato. Poco calo = più robusta (mai una garanzia).
        </p>
      </section>

      <section className="panel">
        <header className="panel-head"><h2>Equity netta · strategia vs Buy&Hold</h2></header>
        <EquityChart eq={r.equity} />
        <p className="muted small">Linea piena = strategia (netta); tratteggiata = buy-and-hold (netto). La barra verticale segna l’inizio dell’out-of-sample.</p>
      </section>

      <section className="panel">
        <header className="panel-head">
          <h2>Significatività (bootstrap) <InfoTip text={BH.bootstrap.text} label={BH.bootstrap.label} /></h2>
          <span className="muted small">{boot.n_iter} ricampionamenti · ambito {boot.scope === 'out_of_sample' ? 'out-of-sample' : 'intero'}</span>
        </header>
        <div className="stat-grid">
          <Stat label="Sharpe (ann.)" value={fmtNum(boot.sharpe_ann, 2)} />
          <Stat label="CI 95% Sharpe" value={`${fmtNum(boot.sharpe_ci95[0], 2)} … ${fmtNum(boot.sharpe_ci95[1], 2)}`} />
          <Stat label="P(non > fortuna)" tip={BH.p_luck} value={fmtPct(boot.p_not_better_than_luck * 100)} cls={boot.p_not_better_than_luck > 0.1 ? 'warn' : ''} />
          <Stat label="P(non > B&H)" value={fmtPct(boot.p_not_better_than_bh * 100)} cls={boot.p_not_better_than_bh > 0.1 ? 'warn' : ''} />
        </div>
        <p className="muted small">{boot.note}</p>
      </section>

      <details className="factors">
        <summary>Metriche complete (full &amp; in-sample, lordo/netto)</summary>
        <FullTable r={r} />
      </details>
    </>
  )
}

function FullTable({ r }) {
  const rows = [
    ['Full · NET', r.metrics.full.net], ['Full · GROSS', r.metrics.full.gross],
    ['Full · B&H', r.metrics.full.bh_net], ['In-sample · NET', r.metrics.in_sample.net],
    ['In-sample · B&H', r.metrics.in_sample.bh_net], ['OOS · NET', r.metrics.out_of_sample.net],
    ['OOS · B&H', r.metrics.out_of_sample.bh_net],
  ]
  return (
    <div className="risk-table-wrap">
      <table className="risk-table">
        <thead><tr><th>Serie</th><th>Tot</th><th>CAGR</th><th>Sharpe</th><th>MaxDD</th><th>Trade</th></tr></thead>
        <tbody>
          {rows.map(([label, m]) => (
            <tr key={label}>
              <td>{label}</td>
              <td className={signClass(m.total_return)}>{fmtPct(m.total_return * 100)}</td>
              <td>{m.cagr == null ? '—' : fmtPct(m.cagr * 100)}</td>
              <td>{fmtNum(m.sharpe, 2)}</td>
              <td className="neg">{fmtPct(m.max_drawdown * 100)}</td>
              <td className="muted">{fmtNum(m.n_trades, 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// --- scan ------------------------------------------------------------
function ScanView({ r }) {
  const d = r.deflated || {}
  const dsr = d.deflated_sharpe
  const best = r.best || {}
  const cons = best.consistency || {}
  return (
    <>
      <section className="panel">
        <header className="panel-head">
          <h2>Controllo data-snooping <InfoTip text={BH.deflated.text} label={BH.deflated.label} /></h2>
          <span className="muted small">{r.n_trials} tentativi{r.capped ? ' (limitati)' : ''} · solo il meglio è atteso sembrare buono per caso</span>
        </header>
        <div className="stat-grid">
          <Stat label="N° tentativi" value={fmtNum(r.n_trials, 0)} />
          <Stat label="Sharpe deflazionato" tip={BH.deflated} value={dsr == null ? '—' : fmtPct(dsr * 100)} cls={dsrClass(dsr)} />
          <Stat label="Best Sharpe (OOS, ann.)" value={fmtNum(best.oos_sharpe_ann_median, 2)} />
          <Stat label="Soglia attesa per caso" value={fmtNum(d.expected_max_sharpe_pp, 3)} />
        </div>
        <p className={`honest-note`}>
          Lo Sharpe deflazionato è {dsr == null ? '—' : fmtPct(dsr * 100)}: probabilità che il migliore tra {r.n_trials} tentativi
          abbia edge vero oltre quanto atteso per puro caso. {dsr != null && dsr < 0.9 ? 'Basso → probabile illusione da data-snooping.' : 'Alto → più robusto, mai una certezza.'}
        </p>
      </section>

      <section className="panel">
        <header className="panel-head"><h2>Distribuzione di TUTTI i tentativi</h2></header>
        <Histogram values={r.distribution.oos_sharpe_ann} best={best.oos_sharpe_ann_median} />
        <p className="muted small">Sharpe OOS (annualizzato) su tutti i {r.n_trials} tentativi — non solo il migliore. Una distribuzione centrata su ~0 con un best alto è il marchio del data-snooping.</p>
      </section>

      <section className="panel">
        <header className="panel-head"><h2>Migliore tentativo · coerenza multi-strumento</h2></header>
        <p><strong>{best.rule}</strong> <code>{JSON.stringify(best.params)}</code></p>
        <div className="stat-grid">
          <Stat label="Strumenti" value={fmtNum(cons.n_instruments, 0)} />
          <Stat label="% Sharpe OOS &gt; 0" tip={BH.consistency} value={cons.share_positive_oos_sharpe == null ? '—' : fmtPct(cons.share_positive_oos_sharpe * 100)} />
          <Stat label="% batte B&H (OOS)" value={cons.share_beats_buy_hold_oos == null ? '—' : fmtPct(cons.share_beats_buy_hold_oos * 100)} />
          <Stat label="Sharpe OOS mediano" value={fmtNum(cons.median_oos_sharpe, 2)} />
        </div>
        <div className="risk-table-wrap">
          <table className="risk-table">
            <thead><tr><th>Strumento</th><th>Sharpe OOS</th><th>Rend. OOS</th><th>vs B&H</th></tr></thead>
            <tbody>
              {(cons.per_instrument || []).map((p) => (
                <tr key={p.instrument}>
                  <td>{p.instrument}</td>
                  <td className={signClass(p.oos_sharpe)}>{fmtNum(p.oos_sharpe, 2)}</td>
                  <td className={signClass(p.oos_total_return)}>{fmtPct(p.oos_total_return * 100)}</td>
                  <td className={signClass(p.oos_excess_vs_bh)}>{fmtPct(p.oos_excess_vs_bh * 100)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}

// --- small components ------------------------------------------------
function EquityChart({ eq }) {
  const { points, splitX, w, h } = useMemo(() => buildChart(eq), [eq])
  if (!points) return <p className="muted small">Equity non disponibile.</p>
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="equity-chart" preserveAspectRatio="none" role="img" aria-label="equity curve">
      {splitX != null && <line x1={splitX} y1="0" x2={splitX} y2={h} className="eq-split" />}
      <polyline className="eq-bh" points={points.bh} fill="none" />
      <polyline className="eq-strat" points={points.strat} fill="none" />
    </svg>
  )
}

function buildChart(eq) {
  if (!eq?.strat_net?.length) return {}
  const w = 600, h = 200, pad = 4
  const s = eq.strat_net, b = eq.bh_net, n = s.length
  const lo = Math.min(...s, ...b), hi = Math.max(...s, ...b)
  const span = hi - lo || 1
  const X = (i) => pad + (i / (n - 1)) * (w - 2 * pad)
  const Y = (v) => h - pad - ((v - lo) / span) * (h - 2 * pad)
  const line = (arr) => arr.map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(' ')
  let splitX = null
  if (eq.split_date) {
    const k = eq.dates.findIndex((d) => d >= eq.split_date)
    if (k > 0) splitX = X(k)
  }
  return { points: { strat: line(s), bh: line(b) }, splitX, w, h }
}

function Histogram({ values, best }) {
  if (!values?.length) return null
  const lo = Math.min(...values), hi = Math.max(...values)
  const bins = 12
  const span = hi - lo || 1
  const counts = new Array(bins).fill(0)
  values.forEach((v) => {
    const idx = Math.min(bins - 1, Math.floor(((v - lo) / span) * bins))
    counts[idx] += 1
  })
  const maxC = Math.max(...counts)
  const bestBin = Math.min(bins - 1, Math.floor(((best - lo) / span) * bins))
  return (
    <div className="hist">
      {counts.map((c, i) => (
        <div key={i} className="hist-col" title={`${(lo + (i / bins) * span).toFixed(2)} … ${c}`}>
          <div className={`hist-bar ${i === bestBin ? 'hist-best' : ''}`} style={{ height: `${(c / maxC) * 100}%` }} />
        </div>
      ))}
      <div className="hist-axis"><span>{fmtNum(lo, 2)}</span><span>Sharpe OOS →</span><span>{fmtNum(hi, 2)}</span></div>
    </div>
  )
}

function Stat({ label, value, cls = '', tip }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}{tip && <> <InfoTip text={tip.text} label={tip.label} /></>}</span>
      <span className={`stat-value ${cls}`}>{value}</span>
    </div>
  )
}

function Caveats({ items }) {
  if (!items?.length) return null
  return (
    <section className="panel">
      <header className="panel-head"><h2>Onestà</h2></header>
      <ul className="tight caveat-list">{items.map((c, i) => <li key={i} className="muted small">{c}</li>)}</ul>
    </section>
  )
}

function signClass(v) { return v == null ? '' : v > 0 ? 'pos' : v < 0 ? 'neg' : '' }
function degClass(retained) {
  if (retained == null) return 'unknown'
  if (retained >= 70) return 'aligned'
  if (retained >= 30) return 'mild'
  return 'notable'
}
function dsrClass(dsr) {
  if (dsr == null) return ''
  if (dsr >= 0.95) return 'pos'
  if (dsr >= 0.9) return 'warn'
  return 'neg'
}

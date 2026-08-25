import { useCallback, useEffect, useState } from 'react'
import { fetchProspectsList, fetchProspects } from '../api/data'
import { fmtNum, fmtPct } from '../lib/format'

// EPISODI — rare multi-year patterns shown one by one (date, context, outcome),
// with n declared and NO percentage under threshold. Read them, don't average.
// Data comes from the saved prospects snapshot (`episodes`).
export default function Episodes() {
  const [symbols, setSymbols] = useState([])
  const [symbol, setSymbol] = useState('')
  const [snap, setSnap] = useState(null)

  useEffect(() => {
    fetchProspectsList().then(({ data }) => {
      const list = data || []
      setSymbols(list)
      setSymbol((s) => s || list.find((r) => r.symbol === '^NDX')?.symbol || list[0]?.symbol || '')
    })
  }, [])
  const load = useCallback(() => { if (symbol) fetchProspects(symbol).then(({ data }) => setSnap(data?.snapshot || null)) }, [symbol])
  useEffect(() => { load() }, [load])

  const ep = snap?.episodes || {}
  return (
    <div className="desk">
      <section className="panel">
        <header className="panel-head">
          <h2>Episodi (pattern pluriennali)</h2>
          <span className="muted small">casi rari, da leggere uno per uno · niente probabilità sotto soglia</span>
        </header>
        {symbols.length > 0 && (
          <div className="desk-controls">
            <label>Strumento
              <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
                {symbols.map((s) => <option key={s.symbol} value={s.symbol}>{s.name ? `${s.name} (${s.symbol})` : s.symbol}</option>)}
              </select></label>
          </div>
        )}
        <p className="honest-note">Questi pattern hanno pochissimi casi: una percentuale da n&lt;10 sarebbe fuorviante. Sono <strong>episodi da leggere</strong>, non statistica.</p>
      </section>

      <EpisodeBlock e={ep.drawdown} kind="drawdown" />
      {ep.bull_year && <EpisodeBlock e={ep.bull_year} kind="bull" />}
      {!snap && <p className="muted small">Nessuno snapshot per {symbol}.</p>}
    </div>
  )
}

function EpisodeBlock({ e, kind }) {
  if (!e) return null
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>{e.label}</h2>
        <span className={`chip ${e.percentage_allowed ? '' : 'warnish'}`}>n = {e.n}</span>
      </header>
      {e.n === 0 ? <p className="muted small">Nessun episodio nel periodo osservato.</p> : (
        <div className="risk-table-wrap">
          <table className="risk-table">
            {kind === 'drawdown' ? (
              <>
                <thead><tr><th>Picco</th><th>Minimo</th><th>Profondità</th><th>Recupero</th><th>+1a dal minimo</th></tr></thead>
                <tbody>{e.episodes.map((x, i) => (
                  <tr key={i}>
                    <td className="muted small">{x.peak_date}</td>
                    <td className="muted small">{x.trough_date}</td>
                    <td className="neg">{fmtPct(x.depth * 100)}</td>
                    <td className="muted small">{x.recover_date || (x.ongoing ? 'in corso' : '—')}</td>
                    <td className={x.forward_after_trough == null ? 'muted' : x.forward_after_trough >= 0 ? 'pos' : 'neg'}>{x.forward_after_trough == null ? '—' : fmtPct(x.forward_after_trough * 100)}</td>
                  </tr>
                ))}</tbody>
              </>
            ) : (
              <>
                <thead><tr><th>Anno</th><th>Run</th><th>Anno dopo</th><th>Rend. anno dopo</th></tr></thead>
                <tbody>{e.episodes.map((x, i) => (
                  <tr key={i}>
                    <td>{x.year}</td>
                    <td className="muted">{x.run_length}º</td>
                    <td className="muted small">{x.next_year || '—'}</td>
                    <td className={x.next_year_return == null ? 'muted' : x.next_year_return >= 0 ? 'pos' : 'neg'}>{x.next_year_return == null ? '—' : fmtPct(x.next_year_return * 100)}</td>
                  </tr>
                ))}</tbody>
              </>
            )}
          </table>
        </div>
      )}
      <p className="muted small caveat">{e.caveat}</p>
    </section>
  )
}

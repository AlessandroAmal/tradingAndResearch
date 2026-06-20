import { fmtPct } from '../lib/format'

// Watchlist of instruments with last close + daily change.
export default function Watchlist({ rows, selected, onSelect, loading, error }) {
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Watchlist</h2>
        {loading && <span className="muted">refreshing…</span>}
      </header>

      {error && <p className="error">Feed unavailable — {error}</p>}
      {!error && rows.length === 0 && !loading && (
        <p className="muted">No instruments. Run the worker seed.</p>
      )}

      <ul className="watchlist">
        {rows.map((r) => {
          const up = (r.changePct ?? 0) >= 0
          return (
            <li
              key={r.id}
              className={`watch-row ${selected === r.id ? 'active' : ''}`}
              onClick={() => onSelect(r.id)}
            >
              <div className="watch-main">
                <span className="sym">{r.symbol}</span>
                <span className="name">{r.name || ''}</span>
              </div>
              <div className="watch-vals">
                <span className="last">
                  {r.last != null ? r.last.toFixed(2) : '—'}
                </span>
                <span className={`chg ${up ? 'pos' : 'neg'}`}>
                  {r.changePct != null ? fmtPct(r.changePct) : '—'}
                </span>
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

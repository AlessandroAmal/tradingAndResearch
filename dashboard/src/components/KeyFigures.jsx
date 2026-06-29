import { useEffect, useState } from 'react'
import { fetchKeyFigures } from '../api/data'

// "Key Figures" feed: each statement with the figure, affected instruments,
// and a one-line "why it matters" (AI impact mapping). Synthesis only —
// shown as possible influence, never as certainty (CLAUDE.md §5).
export default function KeyFigures({ refreshKey = 0 }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchKeyFigures(15).then(({ data, error }) => {
      if (cancelled) return
      if (error) setError(error.message)
      setItems(data || [])
      setLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [refreshKey])

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Key figures</h2>
        {loading && <span className="muted small">loading…</span>}
      </header>

      {error && <p className="error">Key figures unavailable — {error}</p>}
      {!error && items.length === 0 && !loading && (
        <p className="muted small">No statements yet. Run the worker figures + impact jobs.</p>
      )}

      <ul className="figures">
        {items.map((s) => (
          <li key={s.id} className="figure-row">
            <div className="figure-head">
              <span className="figure-name">{s.figure}</span>
              {s.role && <span className="muted small">{s.role}</span>}
              {s.stated_at && (
                <span className="muted small">
                  {new Date(s.stated_at).toLocaleDateString()}
                </span>
              )}
            </div>

            <div className="figure-text">
              {s.url ? (
                <a href={s.url} target="_blank" rel="noopener noreferrer">{s.statement}</a>
              ) : (
                s.statement
              )}
            </div>

            {Array.isArray(s.affected_instruments) && s.affected_instruments.length > 0 && (
              <div className="figure-instr">
                {s.affected_instruments.map((sym) => (
                  <span key={sym} className="pill">{sym}</span>
                ))}
              </div>
            )}

            {s.why_it_matters && (
              <div className="figure-why muted small">{s.why_it_matters}</div>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}

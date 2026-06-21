import { useEffect, useState } from 'react'
import { fetchNewsForInstrument } from '../api/data'

// "Recent relevant news" for one instrument, filtered by the AI tags
// (news_items.instruments[] contains this symbol).
export default function InstrumentNews({ symbol }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!symbol) return
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchNewsForInstrument(symbol, 8).then(({ data, error }) => {
      if (cancelled) return
      if (error) setError(error.message)
      setItems(data || [])
      setLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [symbol])

  return (
    <div className="inst-news">
      <div className="panel-head">
        <h3>Recent relevant news</h3>
        {loading && <span className="muted small">loading…</span>}
      </div>
      {error && <p className="error small">News unavailable — {error}</p>}
      {!error && items.length === 0 && !loading && (
        <p className="muted small">No tagged news for {symbol} yet.</p>
      )}
      <ul className="news-list">
        {items.map((n) => (
          <li key={n.id} className="news-row">
            <a href={n.url} target="_blank" rel="noopener noreferrer">{n.title}</a>
            <div className="muted small">
              {n.source}
              {n.published_at ? ` · ${new Date(n.published_at).toLocaleDateString()}` : ''}
              {Array.isArray(n.themes) && n.themes.length > 0
                ? ` · ${n.themes.join(', ')}`
                : ''}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

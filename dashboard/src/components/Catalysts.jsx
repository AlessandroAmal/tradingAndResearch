import { countdown } from '../lib/format'

// "Next catalysts" widget: upcoming events with a live-ish countdown.
export default function Catalysts({ events, loading, error, nowMs }) {
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Next catalysts</h2>
        {loading && <span className="muted">loading…</span>}
      </header>

      {error && <p className="error">Calendar feed unavailable — {error}</p>}
      {!error && events.length === 0 && !loading && (
        <p className="muted">No upcoming events.</p>
      )}

      <ul className="catalysts">
        {events.map((e) => (
          <li key={e.id} className="cat-row">
            <div className="cat-main">
              <span className={`imp imp-${e.importance || 'low'}`} />
              <div>
                <div className="cat-title">{e.title}</div>
                <div className="muted small">
                  {e.country ? `${e.country} · ` : ''}
                  {new Date(e.event_time).toLocaleString()}
                </div>
              </div>
            </div>
            <span className="countdown">{countdown(e.event_time, nowMs)}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

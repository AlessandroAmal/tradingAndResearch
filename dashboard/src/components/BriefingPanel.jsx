import { useEffect, useState } from 'react'
import { fetchLatestBriefing } from '../api/data'

// Home panel: latest morning + intraday AI briefing.
// The uncertainty note is always shown — synthesis is never presented
// as certainty (CLAUDE.md §5).
export default function BriefingPanel() {
  const [morning, setMorning] = useState(null)
  const [intraday, setIntraday] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    Promise.all([fetchLatestBriefing('morning'), fetchLatestBriefing('intraday')]).then(
      ([m, i]) => {
        if (cancelled) return
        if (m.error || i.error) setError((m.error || i.error).message)
        setMorning(m.data || null)
        setIntraday(i.data || null)
        setLoading(false)
      },
    )
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Briefing</h2>
        {loading && <span className="muted small">loading…</span>}
      </header>

      {error && <p className="error">Briefings unavailable — {error}</p>}
      {!error && !morning && !intraday && !loading && (
        <p className="muted small">No briefing yet. Run the worker AI jobs.</p>
      )}

      <Briefing label="Intraday — what matters now" b={intraday} />
      <Briefing label="Morning" b={morning} />
    </section>
  )
}

function Briefing({ label, b }) {
  if (!b) return null
  return (
    <article className="briefing">
      <div className="briefing-head">
        <span className="briefing-label">{label}</span>
        <span className="muted small">
          {b.generated_at ? new Date(b.generated_at).toLocaleString() : ''}
        </span>
      </div>
      {Array.isArray(b.themes_covered) && b.themes_covered.length > 0 && (
        <div className="briefing-themes">
          {b.themes_covered.map((t) => (
            <span key={t} className="pill">{t}</span>
          ))}
        </div>
      )}
      <pre className="briefing-body">{b.body}</pre>
      {b.uncertainty_note && (
        <p className="briefing-caveat">⚠ {b.uncertainty_note}</p>
      )}
    </article>
  )
}

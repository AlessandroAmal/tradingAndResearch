import { useCallback, useEffect, useState } from 'react'
import { fetchLatestBriefing } from '../api/data'
import { generateBriefing, apiConfigured } from '../api/control'

// Home panel: latest morning + intraday AI briefing.
// Re-reads when `refreshKey` changes (i.e. on "Aggiorna"). The briefing is AI
// (paid), so the free Aggiorna only RE-READS the latest one; "Genera ora"
// produces a fresh one on demand. The uncertainty note is always shown —
// synthesis is never presented as certainty (CLAUDE.md §5).
export default function BriefingPanel({ refreshKey = 0 }) {
  const [morning, setMorning] = useState(null)
  const [intraday, setIntraday] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [gen, setGen] = useState({ loading: false, error: null })

  const load = useCallback(async () => {
    setLoading(true)
    const [m, i] = await Promise.all([fetchLatestBriefing('morning'), fetchLatestBriefing('intraday')])
    if (m.error || i.error) setError((m.error || i.error).message)
    setMorning(m.data || null)
    setIntraday(i.data || null)
    setLoading(false)
  }, [])

  // Re-fetch on mount and whenever the page is refreshed (Aggiorna bumps refreshKey).
  useEffect(() => { load() }, [load, refreshKey])

  const runGenerate = useCallback(async () => {
    setGen({ loading: true, error: null })
    const { error } = await generateBriefing('intraday')
    if (error) { setGen({ loading: false, error: error.message }); return }
    setGen({ loading: false, error: null })
    load() // re-read the freshly generated briefing
  }, [load])

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Briefing</h2>
        <div className="briefing-actions">
          {loading && <span className="muted small">loading…</span>}
          <button className="ghost small" onClick={runGenerate} disabled={gen.loading || !apiConfigured}
            title="Genera un briefing intraday aggiornato (usa l’API Anthropic, a pagamento)">
            {gen.loading ? 'Genero…' : '↻ Genera ora (AI)'}
          </button>
        </div>
      </header>

      {gen.error && <p className="error">Generazione non riuscita — {gen.error}</p>}
      {!apiConfigured && <p className="muted small">Configura l’API locale per generare on-demand; altrimenti i briefing arrivano dallo scheduler.</p>}
      {error && <p className="error">Briefings unavailable — {error}</p>}
      {!error && !morning && !intraday && !loading && (
        <p className="muted small">Nessun briefing ancora. Premi “Genera ora” o attendi lo scheduler.</p>
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

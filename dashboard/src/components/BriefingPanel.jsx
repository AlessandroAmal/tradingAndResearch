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

  // Generate a specific kind on demand (both are paid). Lets the user un-stick
  // Morning or Intraday immediately instead of waiting for the daily scheduler.
  const runGenerate = useCallback(async (kind) => {
    setGen({ loading: kind, error: null })
    const { error } = await generateBriefing(kind)
    if (error) { setGen({ loading: false, error: error.message }); return }
    setGen({ loading: false, error: null })
    load() // re-read the freshly generated briefing
  }, [load])

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Briefing</h2>
        {loading && <span className="muted small">loading…</span>}
      </header>

      {gen.error && <p className="error">Generazione non riuscita — {gen.error}</p>}
      {!apiConfigured && <p className="muted small">Configura l’API locale per generare on-demand; altrimenti i briefing arrivano dallo scheduler.</p>}
      {error && <p className="error">Briefings unavailable — {error}</p>}
      {!error && !morning && !intraday && !loading && (
        <p className="muted small">Nessun briefing ancora. Premi “Genera ora” o attendi lo scheduler.</p>
      )}

      <Briefing label="Intraday — what matters now" b={intraday}
        onGenerate={() => runGenerate('intraday')} busy={gen.loading} kind="intraday" />
      <Briefing label="Morning" b={morning}
        onGenerate={() => runGenerate('morning')} busy={gen.loading} kind="morning" />
    </section>
  )
}

function Briefing({ label, b, onGenerate, busy, kind }) {
  return (
    <article className="briefing">
      <div className="briefing-head">
        <span className="briefing-label">{label}</span>
        <span className="muted small">
          {b?.generated_at ? new Date(b.generated_at).toLocaleString() : 'mai generato'}
          {onGenerate && (
            <> · <button className="ghost small" onClick={onGenerate} disabled={!!busy || !apiConfigured}
              title="Genera un briefing aggiornato (usa l’API Anthropic, a pagamento)">
              {busy === kind ? 'Genero…' : '↻ Genera ora (AI)'}
            </button></>
          )}
        </span>
      </div>
      {!b && <p className="muted small">Nessun briefing di questo tipo. Premi “Genera ora”.</p>}
      {b && (<>
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
      </>)}
    </article>
  )
}

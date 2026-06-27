import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchDecisionBoards, fetchDecisionBoard } from '../api/data'
import { generateAi, apiConfigured } from '../api/control'
import { probAbove } from '../lib/options'
import { fmtNum, fmtPct, countdown, relativeTime, pluralize } from '../lib/format'
import InfoTip from '../components/InfoTip'
import { DECISION_HELP_BY_KEY as DH } from '../data/guide'

// Decision board (M9) — per-instrument confluence cockpit (gold first).
// NOT a signal and NEVER a prediction: it lays out the context the user weighs.
// Snapshots are produced by `python -m app.main decision` (worker).
export default function DecisionBoard() {
  const [symbols, setSymbols] = useState([])
  const [symbol, setSymbol] = useState('')
  const [board, setBoard] = useState(null)
  const [meta, setMeta] = useState(null)
  const [error, setError] = useState(null)
  const [nowMs, setNowMs] = useState(Date.now())
  const [level, setLevel] = useState('')              // user price level (shared)
  const [ai, setAi] = useState({ loading: false, error: null })

  useEffect(() => {
    const t = setInterval(() => setNowMs(Date.now()), 30_000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    fetchDecisionBoards().then(({ data, error }) => {
      if (error) { setError(error.message); return }
      const rows = data || []
      setSymbols(rows)
      if (rows.length) setSymbol(rows[0].symbol)
    })
  }, [])

  const loadBoard = useCallback(() => {
    if (!symbol) return
    fetchDecisionBoard(symbol).then(({ data, error }) => {
      if (error) { setError(error.message); return }
      setMeta(data || null)
      setBoard(data?.board || null)
    })
  }, [symbol])

  useEffect(() => { loadBoard() }, [loadBoard])

  const runAi = useCallback(async () => {
    setAi({ loading: true, error: null })
    const lvl = level !== '' && !Number.isNaN(Number(level)) ? Number(level) : null
    const { error } = await generateAi(symbol, lvl)
    if (error) { setAi({ loading: false, error: error.message }); return }
    setAi({ loading: false, error: null })
    loadBoard()  // re-read so the saved AI summary shows
  }, [symbol, level, loadBoard])

  return (
    <div className="desk">
      <section className="panel">
        <header className="panel-head">
          <h2>Decision board</h2>
          <span className="muted small">il quadro che pesi tu · non è un segnale, non è una previsione</span>
        </header>

        {error && <p className="error">Decision board non disponibile — {error}</p>}
        {symbols.length === 0 && !error && (
          <p className="muted small">
            Nessuno snapshot. Esegui <code>python -m app.main decision</code> (serve FRED_API_KEY),
            oppure premi <strong>Aggiorna</strong> in alto (richiede l’API locale).
          </p>
        )}

        {symbols.length > 0 && (
          <div className="desk-controls">
            <label>Strumento
              <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
                {symbols.map((s) => <option key={s.symbol} value={s.symbol}>{s.name || s.symbol}</option>)}
              </select>
            </label>
            {board?.last != null && <span className="chip">ultimo {fmtNum(board.last, 2)}</span>}
            {meta?.snapshot_at && (
              <span className="muted small">
                calcolato {relativeTime(meta.snapshot_at, nowMs)}
                {' '}· {new Date(meta.snapshot_at).toLocaleString()}
              </span>
            )}
          </div>
        )}
      </section>

      {board && (
        <>
          <SynthesisSection synthesis={board.synthesis} implied={board.implied} />
          <ConfluenceBoard rows={board.confluence || []} nowMs={nowMs} />
          <BaseRatePanel br={board.base_rate} />
          <ImpliedPanel implied={board.implied} level={level} onLevelChange={setLevel} />
          <AISummary s={board.ai_summary} onRun={runAi} ai={ai} level={level} />
          <Context drivers={board.macro_drivers} events={board.events} figures={board.figures} nowMs={nowMs} />
        </>
      )}
    </div>
  )
}

// Sintesi (confluence read) — the lean (alignment of CURRENT conditions, NOT a
// probability) + transparent factor breakdown + conditions↔market divergence.
function SynthesisSection({ synthesis, implied }) {
  if (!synthesis) return null
  const { lean, factors = [], market, divergence, caveats = [] } = synthesis
  const dirClass = leanClass(lean?.direction)
  const score = lean?.score
  // bar fill: 0..50% width on the side of the lean (|score|/100 * half-width).
  const pct = score == null ? 0 : Math.min(Math.abs(score), 100) / 2

  return (
    <section className="panel synth">
      <header className="panel-head">
        <h2>Sintesi — lettura di confluenza
          {' '}<InfoTip text={DH.confluence_read.text} label={DH.confluence_read.label} /></h2>
        <span className="muted small">fotografia delle condizioni attuali · non una previsione</span>
      </header>

      {/* a. lean with strength */}
      <div className="lean-head">
        <span className={`lean-label ${dirClass}`}>{lean?.label || '—'}</span>
        {score != null && (
          <span className="muted small">lettura {score > 0 ? '+' : ''}{fmtNum(score, 0)} / 100 · {lean.contributing_factors} fattori</span>
        )}
        <InfoTip text={DH.lean.text} label={DH.lean.label} />
      </div>
      <div className="lean-bar" role="img" aria-label={`lettura ${lean?.label}`}>
        <span className="lean-axis" />
        {score != null && (
          <span
            className={`lean-fill ${dirClass}`}
            style={score >= 0
              ? { left: '50%', width: `${pct}%` }
              : { right: '50%', width: `${pct}%` }}
          />
        )}
      </div>
      <p className="muted small">{lean?.disclaimer}</p>

      {/* a. factor breakdown — expandable, full transparency */}
      <details className="factors">
        <summary>
          Dettaglio per fattore <InfoTip text={DH.factor_breakdown.text} label={DH.factor_breakdown.label} />
        </summary>
        <div className="risk-table-wrap">
          <table className="risk-table">
            <thead><tr><th>Fattore</th><th>Stato</th><th>Tipo</th><th>Peso</th><th>Nota</th></tr></thead>
            <tbody>
              {factors.map((f) => (
                <tr key={f.key} className={f.included ? '' : 'excluded'}>
                  <td>{f.label}</td>
                  <td><span className={`fac ${facClass(f.classification)}`}>{facLabel(f.classification)}</span></td>
                  <td className="muted small">{f.kind === 'context' ? 'contesto' : 'direzionale'}</td>
                  <td className="muted">{f.included ? fmtNum(f.weight, 1) : '—'}</td>
                  <td className="muted small">{f.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      {/* c. conditions vs market */}
      {divergence && (
        <div className={`divergence diverg-${divergence.level}`}>
          <span className="diverg-tag">Condizioni ↔ mercato
            {' '}<InfoTip text={DH.divergence.text} label={DH.divergence.label} /></span>
          <span>{divergence.message}</span>
          {market?.prob_up != null && (
            <span className="muted small">
              {' '}(odds impliciti a ~{market.horizon}g: prob. salga {fmtPct(market.prob_up * 100)})
            </span>
          )}
        </div>
      )}

      {/* d. fixed caveats */}
      <ul className="tight caveat-list">
        {caveats.map((c, i) => <li key={i} className="muted small">{c}</li>)}
      </ul>
    </section>
  )
}

// a. Confluence — every condition at a glance, colour = state only.
function ConfluenceBoard({ rows }) {
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Confluenza</h2>
        <span className="muted small">il colore indica solo lo stato, non un’azione</span>
      </header>
      {rows.length === 0 && <p className="muted small">Dati insufficienti per la confluenza.</p>}
      <div className="conf-grid">
        {rows.map((r) => (
          <div key={r.key} className={`conf-cell conf-${r.state}`}>
            <span className="conf-label">{r.label}</span>
            <span className="conf-value">{typeof r.value === 'number' ? fmtNum(r.value, 2) : (r.value ?? '—')}</span>
            {r.detail && <span className="conf-detail muted small">{r.detail}</span>}
          </div>
        ))}
      </div>
    </section>
  )
}

// b. Base rate — honest history with n ALWAYS visible.
function BaseRatePanel({ br }) {
  if (!br) return null
  const status = br.status
  const dir = { up: 'su', down: 'giù', flat: 'piatti' }[br.direction] || br.direction
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Base rate storico
          {' '}<InfoTip text={DH.base_rate.text} label={DH.base_rate.label} /></h2>
        <span className="muted small">frequenza storica, non una previsione</span>
      </header>

      {status === 'no_streak' && <p className="muted">{br.message || 'Nessuno streak in corso.'}</p>}

      {(status === 'ok' || status === 'insufficient' || status === 'never') && (
        <div className="br-head">
          <span className="chip">
            Streak: {br.length} {pluralize(br.length, 'giorno', 'giorni')} {dir}{br.in_progress ? ' (in corso)' : ''}
          </span>
          <span className={`chip ${status === 'ok' ? '' : 'warnish'}`}>
            n = {br.sample_size}
            {status === 'insufficient' && ` (< ${br.min_sample})`}
          </span>
        </div>
      )}

      {status === 'never' && (
        <p className="honest-note">
          Mai accaduto nel periodo osservato: <strong>nessuna base statistica</strong>. Non viene
          mostrata alcuna probabilità — la rarità non implica un rimbalzo.
        </p>
      )}

      {status === 'insufficient' && (
        <p className="honest-note">
          Campione insufficiente (n = {br.sample_size} &lt; {br.min_sample}):
          <strong> nessuna conclusione</strong>. I numeri sotto sono indicativi, non una base affidabile.
        </p>
      )}

      {(status === 'ok' || status === 'insufficient') && (br.horizons?.length > 0) && (
        <div className="risk-table-wrap">
          <table className="risk-table">
            <thead><tr>
              <th>Orizzonte</th>
              <th>n</th>
              <th><span className="field-label">% in salita <InfoTip text={DH.pct_up.text} label={DH.pct_up.label} /></span></th>
              <th>rend. medio</th>
              <th>mediana</th>
            </tr></thead>
            <tbody>
              {br.horizons.map((h) => (
                <tr key={h.horizon}>
                  <td>+{h.horizon}g</td>
                  <td className={h.n < br.min_sample ? 'warn' : ''}>{h.n}</td>
                  <td>{h.pct_up == null ? '—' : fmtPct(h.pct_up * 100)}</td>
                  <td className={signClass(h.mean_return)}>{h.mean_return == null ? '—' : fmtPct(h.mean_return * 100)}</td>
                  <td className="muted">{h.median_return == null ? '—' : fmtPct(h.median_return * 100)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {br.caveat && <p className="muted small caveat">{br.caveat}</p>}
    </section>
  )
}

// c. Implied probabilities — the market's odds at several horizons, optionally
// at a USER-CHOSEN level K (the useful directional number, not just the ~50/50 ATM).
function ImpliedPanel({ implied, level, onLevelChange }) {
  if (!implied) return null
  const horizons = implied.horizons || []
  const spot = implied.spot
  const r = implied.risk_free_rate ?? 0.04
  const K = level !== '' && !Number.isNaN(Number(level)) ? Number(level) : null

  // Recompute P(above/below K) per horizon from the stored ATM IV (same
  // risk-neutral math as the worker). Falls back to the ATM row when no level.
  const probsFor = (h) => {
    if (!h.available) return { above: null, below: null, ref: null }
    if (K != null && spot && h.atm_iv) {
      const T = (h.days_to_expiry || 0) / 365
      const above = probAbove(spot, K, T, r, h.atm_iv)
      return { above, below: above == null ? null : 1 - above, ref: K }
    }
    return { above: h.prob_up, below: h.prob_down, ref: implied.level }
  }

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Probabilità implicite (opzioni)
          {' '}<InfoTip text={DH.implied_prob.text} label={DH.implied_prob.label} /></h2>
        <span className="muted small">odds del mercato su {implied.underlying} · non una previsione</span>
      </header>

      {horizons.length === 0 && (
        <p className="muted small">{implied.note || 'Probabilità implicite non disponibili.'}</p>
      )}

      {horizons.length > 0 && (
        <>
          <div className="desk-controls">
            <label>Il tuo livello (prezzo)
              <input
                type="number" step="any" inputMode="decimal"
                placeholder={spot != null ? `es. ${fmtNum(spot, 0)}` : 'prezzo'}
                value={level}
                onChange={(e) => onLevelChange(e.target.value)}
              />
            </label>
            {K != null
              ? <span className="chip">prob. sopra/sotto {fmtNum(K, 2)}</span>
              : <span className="muted small">vuoto = ATM (≈ prezzo corrente {fmtNum(implied.level, 2)})</span>}
            {K != null && <button className="ghost small" onClick={() => onLevelChange('')}>azzera</button>}
          </div>

          <div className="risk-table-wrap">
            <table className="risk-table">
              <thead><tr>
                <th>Orizzonte</th>
                <th>Scadenza</th>
                <th><span className="field-label">Movimento atteso ±<InfoTip text={DH.expected_move.text} label={DH.expected_move.label} /></span></th>
                <th>Prob. sopra{K != null ? ` ${fmtNum(K, 2)}` : ''}</th>
                <th>Prob. sotto{K != null ? ` ${fmtNum(K, 2)}` : ''}</th>
              </tr></thead>
              <tbody>
                {horizons.map((h) => {
                  const p = probsFor(h)
                  return (
                    <tr key={h.target_days}>
                      <td>~{h.target_days}{pluralize(h.target_days, 'g', 'g')}</td>
                      <td className="muted">{h.available ? `${h.expiry} (${h.days_to_expiry}g)` : '—'}</td>
                      <td>{h.available ? `±${fmtNum(h.expected_move_pct, 1)}%` : <span className="muted small">{h.note || '—'}</span>}</td>
                      <td className="pos">{p.above != null ? fmtPct(p.above * 100) : '—'}</td>
                      <td className="neg">{p.below != null ? fmtPct(p.below * 100) : '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="muted small">
            Calcolate dalla volatilità implicita ATM (Black-Scholes, risk-neutral)
            {K != null ? ` sul tuo livello ${fmtNum(K, 2)}` : ` sul livello corrente ${fmtNum(implied.level, 2)}`}.
            Sono gli odds impliciti nei prezzi, NON una previsione.
          </p>
        </>
      )}
    </section>
  )
}

// d. AI synthesis — PAID action (separate button). Interprets the REAL
// probabilities + base rates; conditional scenarios; never a directional call.
function AISummary({ s, onRun, ai, level }) {
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Analisi AI</h2>
        <span className="muted small">interpreta le probabilità reali · nessuna chiamata direzionale</span>
      </header>

      <div className="desk-controls">
        <button className="primary" onClick={onRun} disabled={ai.loading || !apiConfigured}>
          {ai.loading ? 'Genero analisi…' : 'Genera analisi AI'}
        </button>
        <span className="muted small">
          💸 a pagamento (usa l’API Anthropic){level !== '' ? ` · userà il livello ${level}` : ''}
        </span>
      </div>
      {!apiConfigured && (
        <p className="muted small">Configura <code>VITE_API_URL</code> e <code>VITE_API_TOKEN</code> e avvia l’API (<code>python -m app.main api</code>).</p>
      )}
      {ai.error && <p className="error">Analisi non riuscita — {ai.error}</p>}

      {!s && !ai.loading && (
        <p className="muted small">Nessuna analisi ancora generata per questo snapshot.</p>
      )}

      {s && (
        <>
          <div className="lean-head">
            <span className="muted small">convinzione (qualitativa):</span>
            <span className={`fac ${convClass(s.conviction)}`}>{s.conviction || '—'}</span>
          </div>
          <p style={{ whiteSpace: 'pre-wrap' }}>{s.read || s.summary}</p>
          {s.upside_drivers?.length > 0 && (
            <>
              <h3 className="ctx-h muted small">Driver di rialzo</h3>
              <ul className="tight">{s.upside_drivers.map((t, i) => <li key={i}>{t}</li>)}</ul>
            </>
          )}
          {s.downside_drivers?.length > 0 && (
            <>
              <h3 className="ctx-h muted small">Driver di ribasso</h3>
              <ul className="tight">{s.downside_drivers.map((t, i) => <li key={i}>{t}</li>)}</ul>
            </>
          )}
          {s.watch_next_event?.length > 0 && (
            <>
              <h3 className="ctx-h muted small">Da monitorare al prossimo evento</h3>
              <ul className="tight">{s.watch_next_event.map((t, i) => <li key={i}>{t}</li>)}</ul>
            </>
          )}
          {s.uncertainty_note && <p className="honest-note">{s.uncertainty_note}</p>}
        </>
      )}
    </section>
  )
}
function convClass(c) {
  return { alta: 'fac-bull', bassa: 'fac-bear' }[c] || 'fac-neutral'
}

// Detail: macro drivers + upcoming events + key-figure statements.
function Context({ drivers, events, figures, nowMs }) {
  return (
    <section className="panel">
      <header className="panel-head"><h2>Contesto</h2></header>

      <h3 className="muted small ctx-h">Driver macro</h3>
      <div className="risk-table-wrap">
        <table className="risk-table">
          <thead><tr><th>Driver</th><th>Valore</th><th>Mov.</th><th>Stato</th><th>Lettura</th></tr></thead>
          <tbody>
            {(drivers || []).map((d) => (
              <tr key={d.id}>
                <td>{d.label}</td>
                <td>{d.value == null ? '—' : fmtNum(d.value, 2)}</td>
                <td>{{ up: '↑', down: '↓', flat: '→' }[d.direction] || '→'}</td>
                <td><span className={`conf-state conf-${d.state}`}>{stateLabel(d.state)}</span></td>
                <td className="muted small">{d.interpretation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 className="muted small ctx-h">Prossimi catalizzatori</h3>
      {(events || []).length === 0 && <p className="muted small">Nessun evento rilevante imminente.</p>}
      <ul className="tight">
        {(events || []).map((e, i) => (
          <li key={i}>
            <strong>{e.title}</strong>{' '}
            <span className="muted small">{e.event_time} · tra {countdown(e.event_time, nowMs)}</span>
          </li>
        ))}
      </ul>

      {(figures || []).length > 0 && (
        <>
          <h3 className="muted small ctx-h">Dichiarazioni key-figure</h3>
          <ul className="tight">
            {figures.map((f, i) => (
              <li key={i}><strong>{f.figure}:</strong> {f.statement}{' '}
                <span className="muted small">{f.stated_at ? new Date(f.stated_at).toLocaleDateString() : ''}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

function stateLabel(state) {
  return { tailwind: 'favorevole', headwind: 'contrario', watch: 'attenzione', neutral: 'neutro' }[state] || state
}
function signClass(v) {
  if (v == null) return ''
  return v > 0 ? 'pos' : v < 0 ? 'neg' : ''
}
// Lean / factor direction -> colour class (direction is market meaning, so it
// reuses the pos/neg hues; never implies an order).
function leanClass(direction) {
  return { bullish: 'lean-bull', bearish: 'lean-bear' }[direction] || 'lean-neutral'
}
function facClass(c) {
  return { bullish: 'fac-bull', bearish: 'fac-bear', caution: 'fac-caution' }[c] || 'fac-neutral'
}
function facLabel(c) {
  return { bullish: 'rialzista', bearish: 'ribassista', caution: 'cautela', neutral: 'neutro' }[c] || c
}

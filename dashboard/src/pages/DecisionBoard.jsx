import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchDecisionBoards, fetchDecisionBoard, fetchProspects } from '../api/data'
import { generateAi, apiConfigured } from '../api/control'
import { probAbove } from '../lib/options'
import { fmtNum, fmtPct, countdown, relativeTime, pluralize } from '../lib/format'
import InfoTip from '../components/InfoTip'
import ConfluenceGauge from '../components/ConfluenceGauge'
import { ProbBar, PercentileBar, RsiBar } from '../components/Indicators'
import { MonitorTestForm, conditionsFromBoard } from '../components/PaperMonitor'
import Prospects from './Prospects'
import { DECISION_HELP_BY_KEY as DH, FX_HELP_BY_KEY as FH, FULLPIC_HELP_BY_KEY as FPH } from '../data/guide'

const HZ_LABEL = { '1s': '1s', '1m': '1m', '3m': '3m', '6m': '6m', '1a': '1a' }

// Collapsible section with an id (for the anchor nav) + default-open by type.
function Fold({ id, title, sub, open = false, children }) {
  return (
    <details id={id} className="asset-fold" open={open}>
      <summary><span className="fold-title">{title}</span>{sub && <span className="muted small fold-sub">{sub}</span>}</summary>
      <div className="fold-body">{children}</div>
    </details>
  )
}

// Prospects snapshot -> per-horizon return distribution rows (options preferred,
// else conditional). RETURNS only (proxy-safe); drawn from the SAVED snapshot.
function prospectRows(snap) {
  if (!snap) return []
  return (snap.horizons || []).filter((h) => h !== '5a').map((h) => {
    const opt = snap.options?.by_horizon?.[h]
    const pair = snap.conditional?.by_horizon?.[h]?.pair
    if (opt?.available && opt.quality?.reliable) {
      return { h, src: 'opzioni', median: opt.median_ret, p16: opt.p16_ret, p84: opt.p84_ret, p2: opt.p2_5_ret, p97: opt.p97_5_ret }
    }
    if (pair?.sufficient) {
      return { h, src: `storico n${pair.n_effective}`, median: pair.median, p16: pair.p16, p84: pair.p84, p2: pair.p2_5, p97: pair.p97_5 }
    }
    return { h, src: null }
  })
}

// Compact fan chart (future) — mirrors Prospects' FanChart, sized for the band.
function BandFan({ rows }) {
  const data = rows.filter((r) => r.src && r.median != null)
  if (data.length < 2) return <p className="muted small">Ventaglio non disponibile (catene sottili / storico insufficiente).</p>
  const W = 300, H = 120, padX = 26, padY = 10
  const xs = data.map((_, i) => padX + (i * (W - 2 * padX)) / (data.length - 1))
  const all = data.flatMap((r) => [r.p2, r.p97]).filter((v) => v != null)
  const lo = Math.min(...all, 0), hi = Math.max(...all, 0)
  const y = (v) => H - padY - ((v - lo) / (hi - lo || 1)) * (H - 2 * padY)
  const band = (a, b) => data.map((r, i) => `${xs[i]},${y(r[a])}`).concat(data.map((r, i) => `${xs[data.length - 1 - i]},${y(r[b])}`)).join(' ')
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="fan-chart" role="img" aria-label="ventaglio prospettive">
      <line x1={padX} y1={y(0)} x2={W - padX} y2={y(0)} className="fan-zero" />
      <polygon points={band('p2', 'p97')} className="fan-95" />
      <polygon points={band('p16', 'p84')} className="fan-68" />
      <polyline points={data.map((r, i) => `${xs[i]},${y(r.median)}`).join(' ')} className="fan-median" />
      {data.map((r, i) => <text key={r.h} x={xs[i]} y={H - 1} className="fan-label">{HZ_LABEL[r.h] || r.h}</text>)}
    </svg>
  )
}

// Decision board (M9) — per-instrument confluence cockpit (gold first).
// NOT a signal and NEVER a prediction: it lays out the context the user weighs.
// Snapshots are produced by `python -m app.main decision` (worker).
export default function DecisionBoard({ initialSymbol = null, instruments, settings, positions, closedPositions, events, priceBySymbol, multiplierBySymbol, onSymbolChange, onSaved }) {
  const [symbols, setSymbols] = useState([])
  const [symbol, setSymbol] = useState(initialSymbol || '')
  const [board, setBoard] = useState(null)
  const [meta, setMeta] = useState(null)
  const [error, setError] = useState(null)
  const [nowMs, setNowMs] = useState(Date.now())
  const [level, setLevel] = useState('')              // user price level (shared)
  const [ai, setAi] = useState({ loading: false, error: null })
  const [prospects, setProspects] = useState(null)    // saved multi-horizon snapshot (fan chart)

  useEffect(() => {
    const t = setInterval(() => setNowMs(Date.now()), 30_000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    fetchDecisionBoards().then(({ data, error }) => {
      if (error) { setError(error.message); return }
      const rows = data || []
      setSymbols(rows)
      setSymbol((cur) => cur || (rows.length ? rows[0].symbol : ''))
    })
  }, [])

  // When opened from the overview, jump to that instrument.
  useEffect(() => {
    if (initialSymbol) setSymbol(initialSymbol)
  }, [initialSymbol])

  // Notify the parent (ASSET) so the price chart above stays in sync with the
  // board's selected symbol.
  useEffect(() => {
    if (symbol) onSymbolChange?.(symbol)
  }, [symbol, onSymbolChange])

  // Multi-horizon prospects snapshot for the top-band fan chart (SAVED snapshot,
  // no recalc needed — the recalc lives in the Prospettive fold).
  useEffect(() => {
    if (!symbol) { setProspects(null); return }
    fetchProspects(symbol).then(({ data }) => setProspects(data?.snapshot || null))
  }, [symbol])

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

  const isStock = !!board?.fundamentals
  const lean = board?.synthesis?.lean
  const market = board?.synthesis?.market
  const fanRows = prospectRows(prospects)

  return (
    <div className="desk asset-view">
      {/* Sticky controls: symbol selector always visible + price + timestamp + test */}
      <div className="asset-controls">
        {symbols.length > 0 && (
          <label className="asset-symbol">Strumento
            <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
              {symbols.map((s) => <option key={s.symbol} value={s.symbol}>{s.name || s.symbol}</option>)}
            </select>
          </label>
        )}
        {board?.last != null && <span className="asset-price">{fmtNum(board.last, 2)}</span>}
        {meta?.snapshot_at && <span className="muted small">calcolato {relativeTime(meta.snapshot_at, nowMs)}</span>}
        {board && instruments && (
          <MonitorTestForm
            symbol={symbol} instruments={instruments} settings={settings}
            multiplier={multiplierBySymbol?.[symbol] ?? 1} multiplierBySymbol={multiplierBySymbol}
            board={board} positions={positions} closedPositions={closedPositions}
            events={events} priceBySymbol={priceBySymbol} conditions={conditionsFromBoard(board)}
            onSaved={onSaved} />
        )}
      </div>

      {error && <p className="error">Decision board non disponibile — {error}</p>}
      {symbols.length === 0 && !error && (
        <p className="muted small">Nessuno snapshot. Premi <strong>Aggiorna</strong> in alto (richiede l’API locale).</p>
      )}

      {board && <EventRiskBanner er={board.event_risk} nowMs={nowMs} />}

      {board && (
        <>
          {/* ================= TOP BAND: conditions | odds | distribution ========= */}
          <section className="asset-band">
            <div className="band-cell band-lancetta">
              <div className="band-label">Condizioni ORA <InfoTip text={DH.lean.text} label={DH.lean.label} /></div>
              <ConfluenceGauge score={lean?.score} label={lean?.label} direction={lean?.direction} />
              {lean?.top_drivers?.length > 0 && (
                <p className="muted small band-drivers">guidata da: {lean.top_drivers.map((d, i) => (
                  <span key={d.key}>{i > 0 ? ', ' : ''}<span className={signClass(d.contribution)}>{d.label}</span></span>
                ))}</p>
              )}
              <p className="band-caveat">Lettura di <strong>CONDIZIONI</strong> attuali (scomposizione di fattori, potere predittivo debole). NON una previsione.</p>
            </div>

            <div className="band-cell band-odds">
              <div className="band-label">Odds del mercato <InfoTip text={DH.implied_prob.text} label={DH.implied_prob.label} /></div>
              <ProbBar value={market?.prob_up} caption={`Prob. salita${market?.horizon ? ` · ~${market.horizon}g` : ''}`} />
              <label className="band-level">Livello scelto
                <input type="number" step="any" value={level} onChange={(e) => setLevel(e.target.value)}
                  placeholder={board.last != null ? fmtNum(board.last, 0) : 'prezzo'} />
              </label>
              <p className="band-caveat">Probabilità <strong>IMPLICITA</strong> nelle opzioni (risk-neutral): il numero calibrato, gli odds del mercato. Dettaglio per orizzonte sotto.</p>
            </div>

            <div className="band-cell band-fan">
              <div className="band-label">Prospettive — dove può andare <InfoTip text="Distribuzione degli esiti per orizzonte (opzioni risk-neutral + storico con n). Non una previsione puntuale." label="Ventaglio" /></div>
              <BandFan rows={fanRows} />
              {fanRows.some((r) => r.src) && (
                <details className="band-grid-fold">
                  <summary>griglia orizzonti</summary>
                  <div className="risk-table-wrap"><table className="risk-table">
                    <thead><tr><th>Oriz.</th><th>Mediana</th><th>68%</th><th>95%</th><th>Fonte</th></tr></thead>
                    <tbody>{fanRows.filter((r) => r.src).map((r) => (
                      <tr key={r.h}>
                        <td>{HZ_LABEL[r.h] || r.h}</td>
                        <td className={r.median >= 0 ? 'pos' : 'neg'}>{fmtPct(r.median * 100)}</td>
                        <td className="muted small">{fmtPct(r.p16 * 100)}…{fmtPct(r.p84 * 100)}</td>
                        <td className="muted small">{fmtPct(r.p2 * 100)}…{fmtPct(r.p97 * 100)}</td>
                        <td className="muted small">{r.src}</td>
                      </tr>
                    ))}</tbody>
                  </table></div>
                </details>
              )}
              <p className="band-caveat"><strong>DISTRIBUZIONE</strong> di esiti (opzioni risk-neutral / storico con n), non una previsione puntuale.</p>
            </div>
          </section>

          <p className="band-distinction muted small">
            La <strong>lancetta</strong> misura l’allineamento delle CONDIZIONI di oggi (segnale debole, scomposizione di fattori);
            il <strong>ventaglio</strong> è una DISTRIBUZIONE di probabilità degli esiti futuri (dalle opzioni e dallo storico, con n).
            Non sono due versioni della stessa cosa.
          </p>

          {/* Sticky anchor nav */}
          <nav className="asset-anchors" aria-label="Sezioni asset">
            <a href="#mosso">Cosa ha mosso</a>
            {isStock ? <a href="#fond">Fondamentali</a> : <a href="#macro">Macro</a>}
            <a href="#storico">Storico</a>
            {board.fx_signals && <a href="#desk">Desk</a>}
            <a href="#tecnica">Tecnica</a>
            {board.seasonality && <a href="#ciclicita">Ciclicità</a>}
            <a href="#odds">Odds</a>
            <a href="#prospettive">Prospettive</a>
            <a href="#ai">AI</a>
          </nav>

          {/* ================= ORDERED COLLAPSIBLE SECTIONS ====================== */}
          <Fold id="mosso" title="Cosa ha mosso questo + news" open>
            <AttributionBlock a={board.attribution} nowMs={nowMs} />
            {isStock && <StockNewsPanel news={board.news} nowMs={nowMs} />}
            <DollarNote note={board.dollar_note} />
          </Fold>

          {isStock ? (
            <Fold id="fond" title="Fondamentali, utili & sorprese" open>
              <DualLens lenses={board.lenses} boardNote={board.board_note} />
              <FullPicturePanel fp={board.full_picture} />
              <FundamentalsPanel f={board.fundamentals} />
              <EarningsPanel f={board.fundamentals} fx={board.fx_signals} nowMs={nowMs} />
              <AnalystsPanel a={board.fundamentals.analysts} last={board.last} />
            </Fold>
          ) : (
            <Fold id="macro" title="Driver macro + regime + freschezza" open>
              <MacroFreshnessBanner mf={board.macro_freshness} />
              <Context drivers={board.macro_drivers} events={board.events} figures={board.figures} nowMs={nowMs} />
              <FundamentalsNote note={board.fundamentals_note} />
            </Fold>
          )}

          {isStock && (
            <Fold id="macro" title="Driver macro (sfondo)">
              <MacroFreshnessBanner mf={board.macro_freshness} />
              <Context drivers={board.macro_drivers} events={board.events} figures={board.figures} nowMs={nowMs} />
            </Fold>
          )}

          <Fold id="storico" title="Storico condizionato / base rate (con n)">
            <BaseRatePanel br={board.base_rate} />
            <p className="muted small">Lo storico condizionato ai driver (con n effettivo) è nel dettaglio Prospettive qui sotto.</p>
          </Fold>

          {board.fx_signals && (
            <Fold id="desk" title="Segnali desk (skew/RR, expected move, COT)">
              <FxSignals fx={board.fx_signals} nowMs={nowMs} />
            </Fold>
          )}

          <Fold id="tecnica" title="Tecnica + lettura di confluenza (dettaglio)">
            <SynthesisSection synthesis={board.synthesis} implied={board.implied} singleStock={isStock} />
            <ConfluenceBoard rows={board.confluence || []} rsi={board.technicals?.rsi} />
          </Fold>

          {board.seasonality && (
            <Fold id="ciclicita" title="Ciclicità (stagionalità)">
              <SeasonalityPanel s={board.seasonality} />
            </Fold>
          )}

          <Fold id="odds" title="Probabilità implicite — dettaglio per orizzonte + livello">
            <ImpliedPanel implied={board.implied} level={level} onLevelChange={setLevel} />
          </Fold>

          <Fold id="prospettive" title="Prospettive — dettaglio (livello, condizionamento, calibrazione)">
            <Prospects nowMs={nowMs} initialSymbol={symbol} />
          </Fold>

          <Fold id="ai" title="Analisi AI (qualitativa)">
            <AISummary s={board.ai_summary} onRun={runAi} ai={ai} level={level} />
          </Fold>
        </>
      )}
    </div>
  )
}

// The 5 FIXED sections — same for every asset, weighted per instrument so the
// reader knows which one counts most here. Weights are editorial emphasis, never
// a score fused into a direction.
const SECTIONS = [
  { key: 'macro', label: 'Condizioni macro' },
  { key: 'technical', label: 'Condizioni tecniche' },
  { key: 'news', label: 'Narrativa & news' },
  { key: 'cyclicality', label: 'Ciclicità' },
  { key: 'fundamentals', label: 'Fondamentali' },
]
const EMPH = { 3: { t: 'primario', c: 'emph-3' }, 2: { t: 'secondario', c: 'emph-2' },
  1: { t: 'sfondo', c: 'emph-1' }, 0: { t: 'n/d', c: 'emph-0' } }

function SectionGuide({ emphasis }) {
  if (!emphasis) return null
  return (
    <section className="panel section-guide">
      <header className="panel-head">
        <h2>Le 5 sezioni — dove guardare per questo asset</h2>
        <span className="muted small">stesse sezioni per ogni strumento · affiancate, non sommate</span>
      </header>
      <div className="sg-grid">
        {SECTIONS.map((s) => {
          const lvl = emphasis[s.key] ?? 0
          const e = EMPH[lvl] || EMPH[0]
          return (
            <div key={s.key} className={`sg-cell ${e.c}`}>
              <span className="sg-label">{s.label}</span>
              <span className="sg-badge">{e.t}</span>
            </div>
          )
        })}
      </div>
      <p className="muted small caveat">Ogni sezione ha la sua etichetta e il suo orizzonte. Il peso indica quanto conta per QUESTO strumento — non è una previsione né un punteggio direzionale.</p>
    </section>
  )
}

// Section 4 — CICLICITÀ (seasonality). Honest: n always shown, sub-threshold =
// insufficiente, fixed data-snooping caveat, "no significant pattern" stated.
function SeasonalityPanel({ s }) {
  if (!s) return null
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Ciclicità (stagionalità)
          {' '}<InfoTip text={DH.seasonality.text} label={DH.seasonality.label} /></h2>
        <span className="muted small">pattern ricorrenti · frequenza storica, non una previsione</span>
      </header>
      {!s.available ? (
        <p className="honest-note">{s.note || 'Storico insufficiente per la stagionalità.'}</p>
      ) : (
        <>
          {s.years != null && <p className="muted small">Storico ~{fmtNum(s.years, 1)} anni.</p>}
          <SeasonRow title={`Per mese (soglia n≥${s.month_min})`} buckets={s.monthly} />
          <SeasonRow title={`Per giorno della settimana (soglia n≥${s.weekday_min})`} buckets={s.weekday} />
          {!s.any_significant && <p className="honest-note">{s.note}</p>}
        </>
      )}
      <p className="muted small caveat">{s.caveat}</p>
    </section>
  )
}

function SeasonRow({ title, buckets }) {
  return (
    <>
      <h3 className="ctx-h muted small">{title}</h3>
      <div className="season-grid">
        {(buckets || []).map((b) => (
          <div key={b.key} className={`season-cell ${!b.sufficient ? 'insuff' : b.significant ? 'sig' : ''}`}>
            <span className="season-lab">{b.label}</span>
            <span className={`season-val ${b.mean_return == null ? 'muted' : signClass(b.mean_return)}`}>
              {b.mean_return == null ? '—' : fmtPct(b.mean_return * 100)}
            </span>
            <span className="muted small">n={b.n}{!b.sufficient ? ' · insuff.' : b.significant ? ' · |t|>2' : ''}</span>
          </div>
        ))}
      </div>
    </>
  )
}

// Section 5 (macro/commodity) — fundamentals are n/d or instrument-specific.
function FundamentalsNote({ note }) {
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Fondamentali</h2>
        <span className="muted small">non applicabili come per un'azienda</span>
      </header>
      <p className="muted small">{note || 'Non applicabile: per indici, FX e commodity non esistono fondamentali d’azienda (valutazione, utili). La lettura poggia su macro, tecnica e narrativa.'}</p>
    </section>
  )
}

// Dual lens — the SAME board reads differently as a holding vs a <=3-week trade.
// Honest: neither lens is a directional forecast.
function DualLens({ lenses, boardNote }) {
  if (!lenses) return null
  return (
    <section className="panel dual-lens">
      <header className="panel-head">
        <h2>Due lenti — holding vs trade</h2>
        <span className="muted small">lo stesso titolo, letto in due modi · nessuna previsione</span>
      </header>
      <div className="lens-grid">
        <div className="lens-card">
          <span className="lens-tag">📈 Holding (anni)</span>
          <p>{lenses.holding}</p>
        </div>
        <div className="lens-card">
          <span className="lens-tag">⏱ Trade (≤3 settimane)</span>
          <p>{lenses.trade}</p>
        </div>
      </div>
      {boardNote && <p className="honest-note">{boardNote}</p>}
      <p className="muted small caveat">{lenses.note}</p>
    </section>
  )
}

// C) Event-risk banner — structural flag at the top; colour = state only.
function EventRiskBanner({ er, nowMs }) {
  if (!er) return null
  return (
    <section className="panel event-risk-banner">
      <div className="erb-row">
        <span className="erb-tag">⚑ Rischio evento</span>
        <span><strong>{er.title}</strong> tra {countdown(er.event_time, nowMs)}
          {' '}<span className="muted small">({String(er.event_time).slice(0, 16)})</span></span>
        {er.expected_move_pct != null && (
          <span className="chip">movimento atteso ±{fmtNum(er.expected_move_pct, 1)}%</span>
        )}
      </div>
      <p className="muted small">Questa lettura di condizioni può <strong>ribaltarsi</strong> dopo l’evento; il ±% è la magnitudo implicita nelle opzioni, non una direzione.</p>
    </section>
  )
}

// A) Macro-freshness banner — only when some FRED driver is delayed.
function MacroFreshnessBanner({ mf }) {
  if (!mf?.any_stale) return null
  return (
    <section className="panel">
      <p className="gate-line gate-warn">
        <span className="gate-tag">⚠ dati ritardati</span> {mf.note}
        {mf.stale_labels?.length > 0 && <> Serie: <strong>{mf.stale_labels.join(', ')}</strong>.</>}
      </p>
    </section>
  )
}

// B) "Cosa ha mosso questo" — explains the move ALREADY happened, never the next.
function AttributionBlock({ a, nowMs }) {
  if (!a) return null
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Cosa ha mosso questo</h2>
        <span className="muted small">
          {a.move_pct != null ? `movimento recente ${a.move_pct > 0 ? '+' : ''}${fmtNum(a.move_pct, 1)}% · ` : ''}spiega il passato, non prevede
        </span>
      </header>
      {a.chain && (
        <div className="attrib-chain">
          {a.chain.map((step, i) => (
            <span key={i} className="attrib-step">{step}{i < a.chain.length - 1 && <span className="attrib-arrow">→</span>}</span>
          ))}
        </div>
      )}
      {a.attributed ? (
        <ul className="tight">
          {a.items.map((it, i) => (
            <li key={i}>
              <span className={`attrib-kind attrib-${it.kind}`}>{{ event: 'evento', macro: 'macro', news: 'news' }[it.kind]}</span>{' '}
              {it.url ? <a href={it.url} target="_blank" rel="noreferrer">{it.text}</a> : <strong>{it.text}</strong>}
              {it.detail && <span className="muted small"> — {it.detail}</span>}
              {it.when && <span className="muted small"> · {it.kind === 'news' ? relativeTime(it.when, nowMs) : String(it.when).slice(0, 16)}</span>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="honest-note">{a.note}</p>
      )}
      <p className="muted small caveat">{a.label}</p>
    </section>
  )
}

// D) Dollar co-movement — context note for dollar-sensitive instruments.
function DollarNote({ note }) {
  if (!note) return null
  return (
    <section className="panel">
      <p className={`gate-line gate-${note.context === 'favorevole' ? 'info' : 'warn'}`}>
        <span className="gate-tag">$ dollaro</span> {note.text}
      </p>
    </section>
  )
}

// Sintesi (confluence read) — the lean (alignment of CURRENT conditions, NOT a
// probability) + transparent factor breakdown + conditions↔market divergence.
function SynthesisSection({ synthesis, implied, singleStock = false }) {
  if (!synthesis) return null
  const { lean, factors = [], market, divergence, caveats = [], mean_reversion: mr, calibration: cal } = synthesis
  const score = lean?.score
  const top = lean?.top_drivers || []

  return (
    <section className="panel synth">
      <header className="panel-head">
        <h2>Sintesi — lettura di confluenza
          {' '}<InfoTip text={DH.confluence_read.text} label={DH.confluence_read.label} /></h2>
        <span className="muted small">fotografia delle condizioni attuali · non una previsione</span>
      </header>
      {cal && (
        <p className="muted small">🔬 Lancetta <strong>calibrata dall’evidenza</strong> al {new Date(cal.calibrated_at).toLocaleDateString()} (periodo {cal.period_start}…{cal.period_end}, IC a {cal.weight_horizon}g). {cal.note}</p>
      )}

      {singleStock && (
        <p className="honest-note">
          Per un titolo singolo questa lancetta è la scomposizione delle <strong>sole condizioni
          MACRO+TECNICA</strong> (sfondo). La lettura che pesa <strong>TUTTO</strong> (anche
          fondamentali e utili) è l’<strong>analisi AI</strong> qui sopra; gli odds completi sono
          la <strong>probabilità implicita</strong>. I fondamentali NON entrano in questo calcolo.
        </p>
      )}

      {/* a. signature gauge + the calibrated implied probability, equal weight */}
      <div className="synth-top">
        <div className="synth-gauge">
          <ConfluenceGauge score={score} label={lean?.label} direction={lean?.direction} />
          <p className="gauge-caveat">
            Fotografia delle condizioni attuali — NON una previsione, NON un segnale di acquisto/vendita.
          </p>
          {score != null && (
            <p className="muted small" style={{ textAlign: 'center' }}>
              {lean.contributing_factors} fattori <InfoTip text={DH.lean.text} label={DH.lean.label} />
            </p>
          )}
          {top.length > 0 && (
            <p className="muted small" style={{ textAlign: 'center' }}>
              guidata da: {top.map((d, i) => (
                <span key={d.key}>{i > 0 ? ', ' : ''}<span className={signClass(d.contribution)}>{d.label} ({d.contribution > 0 ? '+' : ''}{fmtNum(d.contribution, 0)})</span></span>
              ))}
            </p>
          )}
          {lean?.tech_caveat && <p className="muted small" style={{ textAlign: 'center' }}>{lean.tech_caveat}</p>}
        </div>
        <div className="synth-side">
          <ProbBar value={market?.prob_up}
            caption={`Prob. implicita salita${market?.horizon ? ` · ~${market.horizon}g` : ''}`} />
          <p className="muted small">
            Il numero <strong>calibrato</strong> è questo (implicito nelle opzioni, gli odds del mercato){' '}
            <InfoTip text={DH.implied_prob.text} label={DH.implied_prob.label} /> — la lancetta è solo l’allineamento delle condizioni.
          </p>
          {divergence && (
            <div className={`divergence diverg-${divergence.level}`}>
              <span className="diverg-tag">Condizioni ↔ mercato
                {' '}<InfoTip text={DH.divergence.text} label={DH.divergence.label} /></span>
              <span>{divergence.message}</span>
            </div>
          )}
        </div>
      </div>

      {/* e. mean-reversion trap — fires ONLY when extension drives a counter-trend lean */}
      {mr && (
        <div className="mean-rev-warning">
          <span className="gate-tag">⚠ fallacia dello scommettitore</span>
          <span>{mr.message}</span>
        </div>
      )}

      {/* a. factor breakdown — expandable; contribution makes the driver obvious */}
      <details className="factors">
        <summary>
          Dettaglio per fattore <InfoTip text={DH.factor_breakdown.text} label={DH.factor_breakdown.label} />
        </summary>
        <div className="risk-table-wrap">
          <table className="risk-table">
            <thead><tr><th>Fattore</th><th>Stato</th><th>Tipo</th><th>Peso</th><th>Contributo</th><th>Nota</th></tr></thead>
            <tbody>
              {factors.map((f) => (
                <tr key={f.key} className={f.included ? '' : 'excluded'}>
                  <td>{f.label}</td>
                  <td><span className={`fac ${facClass(f.classification)}`}>{facLabel(f.classification)}</span></td>
                  <td className="muted small">{f.kind === 'context' ? 'contesto' : 'direzionale'}</td>
                  <td className="muted">{f.included ? fmtNum(f.weight, 1) : '—'}</td>
                  <td className={f.contribution != null ? signClass(f.contribution) : 'muted'}>
                    {f.contribution != null ? `${f.contribution > 0 ? '+' : ''}${fmtNum(f.contribution, 0)}` : '—'}
                  </td>
                  <td className="muted small">{f.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted small">Il «Contributo» è il peso segnato di ciascun fattore sul lean (scala −100..+100). Somma dei contributi = lancetta. I fattori di contesto non contribuiscono.</p>
      </details>

      {/* d. fixed caveats */}
      <ul className="tight caveat-list">
        {caveats.map((c, i) => <li key={i} className="muted small">{c}</li>)}
      </ul>
    </section>
  )
}

// a. Confluence — every condition at a glance, colour = state only.
function ConfluenceBoard({ rows, rsi }) {
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Confluenza</h2>
        <span className="muted small">il colore indica solo lo stato, non un’azione</span>
      </header>
      {rsi?.value != null && (
        <RsiBar value={rsi.value} overbought={rsi.overbought} oversold={rsi.oversold} />
      )}
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
          {(() => {
            const avail = horizons.filter((h) => h.available)
            const rep = avail.length ? avail.reduce((a, b) => (b.days_to_expiry > a.days_to_expiry ? b : a)) : null
            const p = rep ? probsFor(rep) : null
            return p && p.above != null
              ? <ProbBar value={p.above} caption={`Prob. sopra ${K != null ? fmtNum(K, 2) : 'livello'} · ~${rep.target_days}g`} />
              : null
          })()}
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
          <thead><tr><th>Driver</th><th>Valore</th><th>Mov.</th><th>Dato al</th><th>Stato</th><th>Lettura</th></tr></thead>
          <tbody>
            {(drivers || []).map((d) => (
              <tr key={d.id}>
                <td>{d.label}</td>
                <td>{d.value == null ? '—' : fmtNum(d.value, 2)}</td>
                <td>{{ up: '↑', down: '↓', flat: '→' }[d.direction] || '→'}</td>
                <td className={d.stale ? 'warn' : 'muted'}>
                  {d.as_of_date || (d.as_of ? String(d.as_of).slice(0, 10) : '—')}
                  {d.stale && <span className="stale-badge" title="dato ritardato"> ⚠ ritardato</span>}
                </td>
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

// FX desk signals (EUR/USD): skew/RR, expected move on events, historical event
// behaviour (with n), COT positioning. All real (priced/measured), not forecasts.
function FxSignals({ fx }) {
  const rr = fx.risk_reversal || []
  const em = fx.expected_move_events || []
  const beh = fx.event_behaviour?.by_event || {}
  const cot = fx.cot
  const behEntries = Object.entries(beh).filter(([, v]) => v && v.n > 0)
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Segnali FX (desk)</h2>
        <span className="muted small">reali: prezzati o misurati · non previsioni</span>
      </header>

      {/* Skew / risk reversal */}
      <h3 className="ctx-h muted small">Skew / Risk reversal <InfoTip text={FH.skew.text} label={FH.skew.label} /></h3>
      {rr.length === 0 && <p className="muted small">Smile opzioni non disponibile.</p>}
      {(() => {
        const repr = rr.find((h) => h.percentile != null)
        return repr ? <PercentileBar pct={repr.percentile} caption={`Risk reversal · percentile (~${repr.target_days}g)`} /> : null
      })()}
      {rr.length > 0 && (
        <div className="risk-table-wrap">
          <table className="risk-table">
            <thead><tr><th>Orizzonte</th><th>RR 25Δ</th><th>Percentile</th><th>Affidabilità</th><th>Bias</th></tr></thead>
            <tbody>
              {rr.map((h) => (
                <tr key={h.target_days}>
                  <td>~{h.target_days}g</td>
                  <td>{h.rr == null ? '—' : h.rr.toFixed(3)}</td>
                  <td>{h.percentile == null ? '—' : `${(h.percentile * 100).toFixed(0)}°`}</td>
                  <td className={h.reliability === 'low' ? 'warn' : 'muted'}>{h.reliability === 'low' ? 'bassa' : 'ok'}</td>
                  <td><span className={`fac ${facClassFromLean(h.lean)}`}>{leanLabel(h.lean)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Expected move on events */}
      <h3 className="ctx-h muted small">Movimento atteso sugli eventi <InfoTip text={FH.expected_move_event.text} label={FH.expected_move_event.label} /></h3>
      {em.length === 0 && <p className="muted small">Nessun evento imminente con scadenza opzioni utile.</p>}
      <ul className="tight">
        {em.map((e, i) => (
          <li key={i}>Il mercato prezza <strong>±{fmtNum(e.expected_move_pct, 1)}%</strong> su «{e.event}» <span className="muted small">({e.event_date}, scad. {e.expiry})</span></li>
        ))}
      </ul>

      {/* Historical event behaviour */}
      <h3 className="ctx-h muted small">Comportamento storico sugli eventi <InfoTip text={FH.event_behaviour.text} label={FH.event_behaviour.label} /></h3>
      {fx.earnings_note && <p className="muted small">⚠ {fx.earnings_note}</p>}
      {behEntries.length === 0 && <p className="muted small">Storico eventi non disponibile.</p>}
      {behEntries.length > 0 && (
        <div className="risk-table-wrap">
          <table className="risk-table">
            <thead><tr><th>Evento</th><th>n</th><th>Mov. mediano</th><th>% prosegue</th><th>% inverte</th></tr></thead>
            <tbody>
              {behEntries.map(([title, v]) => (
                <tr key={title}>
                  <td>{title}</td>
                  <td className={v.status === 'insufficient' ? 'warn' : ''}>{v.n}{v.status === 'insufficient' ? ' (insuff.)' : ''}</td>
                  <td>{v.median_abs_move_pct == null ? '—' : `±${fmtNum(v.median_abs_move_pct, 2)}%`}</td>
                  <td>{v.pct_continued == null ? '—' : fmtPct(v.pct_continued * 100)}</td>
                  <td>{v.pct_reversed == null ? '—' : fmtPct(v.pct_reversed * 100)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* COT positioning */}
      <h3 className="ctx-h muted small">Posizionamento COT <InfoTip text={FH.cot.text} label={FH.cot.label} /></h3>
      {!cot ? (
        <p className="muted small">Non applicabile a questo strumento (nessun COT CFTC) — lo skew delle opzioni è il read di posizionamento.</p>
      ) : cot.state === 'n/d' ? (
        <p className="muted small">{cot.note || 'COT non disponibile.'}</p>
      ) : (
        <>
          <PercentileBar pct={cot.percentile} caption="Posizione netta · percentile (~3a)" />
          <div className="stat-grid">
            <Stat label="Netto" value={cot.net == null ? '—' : fmtNum(cot.net, 0)} />
            <Stat label="Stato" value={cotLabel(cot.state)} cls={cot.state === 'neutral' ? '' : 'warn'} />
            <Stat label="Al" value={cot.as_of || '—'} />
          </div>
          <p className="muted small">{cot.note}</p>
        </>
      )}

      <p className="muted small caveat">{fx.note}</p>
    </section>
  )
}

// --- single-stock panels (fundamentals = context, already priced) ----
function fmtBig(v) {
  if (v == null) return '—'
  const a = Math.abs(v)
  if (a >= 1e12) return `${(v / 1e12).toFixed(2)}T`
  if (a >= 1e9) return `${(v / 1e9).toFixed(1)}B`
  if (a >= 1e6) return `${(v / 1e6).toFixed(1)}M`
  return fmtNum(v, 0)
}
const pctOrNa = (v) => (v == null ? '—' : fmtPct(v * 100).replace('+', ''))
const numOrNa = (v, d = 1) => (v == null ? '—' : fmtNum(v, d))

// QUADRO COMPLETO — all factor states side by side, NOT fused. Implied odds in
// evidence (the only integrated number). Colour = state only.
function FullPicturePanel({ fp }) {
  if (!fp) return null
  const factors = fp.factors || []
  const im = fp.implied || {}
  return (
    <section className="panel fullpic">
      <header className="panel-head">
        <h2>Quadro completo
          {' '}<InfoTip text={DH.confluence_read.text} label={DH.confluence_read.label} /></h2>
        <span className="muted small">tutti i fattori affiancati · il colore indica solo lo stato</span>
      </header>

      {/* Implied odds — highlighted: the integrated, calibrated number. */}
      <div className="fp-odds">
        <ProbBar value={im.prob_up}
          caption={`Odds impliciti · prob. salita${im.horizon ? ` · ~${im.horizon}g` : ''}`} />
        <p className="muted small">{im.label}</p>
      </div>

      <div className="fp-grid">
        {factors.map((x) => (
          <div key={x.key} className={`fp-cell tone-${x.tone || 'none'}`}>
            <span className="fp-label">{x.label}
              {FPH[x.key] && <> <InfoTip text={FPH[x.key].text} label={FPH[x.key].label} /></>}
            </span>
            <span className="fp-state">{x.state}</span>
            <span className="fp-value muted small">{x.value}</span>
          </div>
        ))}
      </div>

      <p className="muted small caveat">{fp.label}</p>
    </section>
  )
}

// Valuation indicator — descriptive (where the multiple sits vs ITSELF), never a
// direction. Percentile bar when a P/E history was reconstructed, else a band.
function ValuationIndicator({ ctx }) {
  if (!ctx || ctx.pe == null) return null
  return (
    <div className="val-indicator">
      {ctx.percentile != null ? (
        <PercentileBar pct={ctx.percentile}
          caption={`Valutazione vs la propria storia · ${ctx.band} (n=${ctx.n})`} />
      ) : (
        <p className="muted small">
          Valutazione: <strong>{ctx.band}</strong> (P/E {ctx.basis} {fmtNum(ctx.pe, 0)}; storia P/E insufficiente per un percentile)
        </p>
      )}
      <p className="muted small">{ctx.note} — non una previsione.</p>
    </div>
  )
}

function FundamentalsPanel({ f }) {
  const val = f.valuation || {}, g = f.growth || {}, q = f.quality || {}, c = f.cash || {}
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Fondamentali</h2>
        <span className="muted small">azienda &amp; valutazione · già riflessi nel prezzo, NON una previsione</span>
      </header>
      <h3 className="ctx-h muted small">Valutazione</h3>
      <div className="stat-grid">
        <Stat label="P/E (trailing)" value={numOrNa(val.pe_trailing)} />
        <Stat label="P/E (forward)" value={numOrNa(val.pe_forward)} />
        <Stat label="P/S" value={numOrNa(val.ps)} />
        <Stat label="P/B" value={numOrNa(val.pb)} />
      </div>
      <ValuationIndicator ctx={val.context} />
      <p className="muted small">{readValuation(val)}</p>

      <h3 className="ctx-h muted small">Crescita &amp; qualità</h3>
      <div className="stat-grid">
        <Stat label="Ricavi YoY" value={pctOrNa(g.revenue_yoy)} cls={signCls(g.revenue_yoy)} />
        <Stat label="Utili YoY" value={pctOrNa(g.earnings_yoy)} cls={signCls(g.earnings_yoy)} />
        <Stat label="Margine lordo" value={pctOrNa(q.gross_margin)} />
        <Stat label="Margine netto" value={pctOrNa(q.net_margin)} />
        <Stat label="Margine oper." value={pctOrNa(q.operating_margin)} />
        <Stat label="ROE" value={pctOrNa(q.roe)} />
      </div>
      <p className="muted small">{readQuality(g, q)}</p>

      <h3 className="ctx-h muted small">Cassa &amp; bilancio</h3>
      <div className="stat-grid">
        <Stat label="Free cash flow" value={fmtBig(c.free_cash_flow)} cls={signCls(c.free_cash_flow)} />
        <Stat label="Op. cash flow" value={fmtBig(c.operating_cash_flow)} />
        <Stat label="Cassa" value={fmtBig(c.cash)} />
        <Stat label="Debito" value={fmtBig(c.debt)} />
        <Stat label="Debt/Equity" value={numOrNa(c.debt_to_equity)} />
      </div>
      <p className="muted small">{readCash(c)}</p>
      <p className="muted small caveat">{f.note}</p>
    </section>
  )
}

function EarningsPanel({ f, fx, nowMs }) {
  const e = f.earnings || {}
  const sur = e.surprises || []
  const em = (fx?.expected_move_events || []).find((x) => /earn|util/i.test(x.event || ''))
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Utili (earnings)</h2>
        <span className="muted small">il catalizzatore dominante di un titolo</span>
      </header>
      <div className="stat-grid">
        <Stat label="Prossimi utili" value={e.next_date || '—'} />
        <Stat label="Tra" value={e.next_date ? countdown(`${e.next_date}T20:00:00Z`, nowMs) : '—'} />
        <Stat label="Consenso EPS" value={e.next_eps_estimate == null ? '—' : fmtNum(e.next_eps_estimate, 2)} />
        <Stat label="EPS fwd" value={e.eps_forward == null ? '—' : fmtNum(e.eps_forward, 2)} />
        {em && <Stat label="Mov. atteso" value={`±${fmtNum(em.expected_move_pct, 1)}%`} />}
      </div>
      {sur.length > 0 ? (
        <>
          <h3 className="ctx-h muted small">Storico sorprese</h3>
          <div className="risk-table-wrap">
            <table className="risk-table">
              <thead><tr><th>Data</th><th>EPS</th><th>Atteso</th><th>Sorpresa</th><th>Esito</th></tr></thead>
              <tbody>
                {sur.map((s) => (
                  <tr key={s.date}>
                    <td>{s.date}</td>
                    <td>{numOrNa(s.reported, 2)}</td>
                    <td className="muted">{numOrNa(s.estimate, 2)}</td>
                    <td className={signCls(s.surprise_pct)}>{s.surprise_pct == null ? '—' : `${fmtNum(s.surprise_pct, 1)}%`}</td>
                    <td><span className={`fac ${s.beat ? 'fac-bull' : 'fac-bear'}`}>{s.beat ? 'beat' : 'miss'}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : <p className="muted small">Storico sorprese non disponibile.</p>}
      <p className="muted small">Il movimento atteso è la magnitudo implicita nelle opzioni, non una direzione.</p>
    </section>
  )
}

function StockNewsPanel({ news, nowMs }) {
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Cosa muove il titolo</h2>
        <span className="muted small">news recenti (nome + ticker)</span>
      </header>
      {(!news || news.length === 0) && <p className="muted small">Nessuna news recente trovata.</p>}
      <ul className="tight">
        {(news || []).map((n, i) => (
          <li key={i}>
            <a href={n.url} target="_blank" rel="noreferrer">{n.title}</a>{' '}
            <span className="muted small">{n.source}{n.published_at ? ` · ${relativeTime(n.published_at, nowMs)}` : ''}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

function AnalystsPanel({ a, last }) {
  if (!a) return null
  const upside = a.target_mean != null && last ? (a.target_mean / last - 1) * 100 : null
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Consenso analisti</h2>
        <span className="muted small">contesto · NON calibrato, non un segnale</span>
      </header>
      <div className="stat-grid">
        <Stat label="Target medio" value={numOrNa(a.target_mean, 2)} />
        <Stat label="vs prezzo" value={upside == null ? '—' : fmtPct(upside)} cls={signCls(upside)} />
        <Stat label="Rating" value={a.recommendation || '—'} />
        <Stat label="N° analisti" value={a.n_analysts == null ? '—' : fmtNum(a.n_analysts, 0)} />
      </div>
      <p className="muted small caveat">I target degli analisti sono contesto, spesso in ritardo e non calibrati: la probabilità calibrata resta quella implicita nelle opzioni.</p>
    </section>
  )
}

function readValuation(v) {
  if (v.pe_forward != null) return `P/E forward ${fmtNum(v.pe_forward, 0)}: ${v.pe_forward > 30 ? 'paghi molto per la crescita attesa' : v.pe_forward < 12 ? 'valutazione contenuta' : 'valutazione media'}.`
  return 'Valutazione: dati parziali (n/d).'
}
function readQuality(g, q) {
  const parts = []
  if (g.revenue_yoy != null) parts.push(`ricavi ${g.revenue_yoy >= 0 ? 'in crescita' : 'in calo'} ${pctOrNa(g.revenue_yoy)} YoY`)
  if (q.net_margin != null) parts.push(`margine netto ${pctOrNa(q.net_margin)}`)
  return parts.length ? `${parts.join(', ')}.` : 'Crescita/qualità: n/d.'
}
function readCash(c) {
  if (c.free_cash_flow != null) return `Free cash flow ${c.free_cash_flow >= 0 ? 'positivo' : 'negativo'} (${fmtBig(c.free_cash_flow)})${c.debt_to_equity != null ? `, debt/equity ${fmtNum(c.debt_to_equity, 0)}` : ''}.`
  return 'Cassa/bilancio: n/d.'
}
function signCls(v) { return v == null ? '' : v > 0 ? 'pos' : v < 0 ? 'neg' : '' }

function Stat({ label, value, cls = '' }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className={`stat-value ${cls}`}>{value}</span>
    </div>
  )
}
function facClassFromLean(lean) {
  return { bullish: 'fac-bull', bearish: 'fac-bear' }[lean] || 'fac-neutral'
}
function leanLabel(lean) {
  return { bullish: 'rialzista', bearish: 'ribassista', neutral: 'neutro' }[lean] || 'n/d'
}
function cotLabel(state) {
  return { crowded_long: 'molto long (rischio reversal)', crowded_short: 'molto short (rischio squeeze)', neutral: 'non estremo' }[state] || state
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

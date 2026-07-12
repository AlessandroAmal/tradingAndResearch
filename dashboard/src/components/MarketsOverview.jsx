import { useEffect, useMemo, useState } from 'react'
import { fetchDecisionBoardsFull } from '../api/data'
import { fmtNum, fmtPct, countdown } from '../lib/format'
import { MiniConfluence } from './Indicators'
import InfoTip from './InfoTip'
import { DECISION_HELP_BY_KEY as DH } from '../data/guide'

// PANORAMICA — orient in 5 seconds and SORT by where to LOOK (not by "success").
// Per instrument: price · mini confluence gauge (conditions) · implied prob (the
// calibrated number) · expected move · DIVERGENCE (conditions vs market) · next
// event. Click a row to open its decision board. Read-only.
const COLS = [
  { key: 'div', label: 'Divergenza', desc: true },
  { key: 'event', label: 'Evento', desc: false },     // soonest first
  { key: 'expmove', label: 'Mov. atteso', desc: true },
  { key: 'lean', label: 'Confluenza', desc: true },    // strength
]

export default function MarketsOverview({ refreshKey = 0, onOpen, nowMs = Date.now() }) {
  const [raw, setRaw] = useState([])
  const [error, setError] = useState(null)
  const [loaded, setLoaded] = useState(false)
  const [sort, setSort] = useState('div')

  useEffect(() => {
    fetchDecisionBoardsFull().then(({ data, error }) => {
      if (error) { setError(error.message); setLoaded(true); return }
      setRaw((data || []).map((r) => summarise(r, nowMs)))
      setLoaded(true)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey])

  const rows = useMemo(() => sortRows(raw, sort), [raw, sort])
  const col = COLS.find((c) => c.key === sort)

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Strumenti — panoramica</h2>
        <span className="muted small">ordina per dove GUARDARE · lancetta = condizioni · prob = implicita</span>
      </header>

      {error && <p className="error small">Panoramica non disponibile — {error}</p>}
      {loaded && !error && rows.length === 0 && (
        <p className="muted small">Nessun decision board ancora. Premi <strong>Aggiorna</strong>.</p>
      )}

      {rows.length > 0 && (
        <div className="ov-table">
          <div className="ov-row ov-head">
            <span>Strumento</span>
            <span className="ov-num">Ultimo <InfoTip text={DH.ov_last.text} label={DH.ov_last.label} /></span>
            <SortBtn col={COLS[3]} sort={sort} setSort={setSort} tip={DH.lean} />
            <span className="ov-num">Prob. salita <InfoTip text={DH.implied_prob.text} label={DH.implied_prob.label} /></span>
            <SortBtn col={COLS[2]} sort={sort} setSort={setSort} num tip={DH.expected_move} />
            <SortBtn col={COLS[0]} sort={sort} setSort={setSort} num tip={DH.ov_divergence} />
            <SortBtn col={COLS[1]} sort={sort} setSort={setSort} tip={DH.ov_next_event} />
          </div>
          {rows.map((r) => (
            <button key={r.symbol} className="ov-row" onClick={() => onOpen?.(r.symbol)} title={`Apri decision board ${r.name}`}>
              <span className="ov-name">{r.name}</span>
              <span className="ov-num">{r.last == null ? '—' : fmtNum(r.last, 2)}</span>
              <MiniConfluence score={r.score} />
              <span className={`ov-num ${r.probUp == null ? 'muted' : ''}`}>{r.probUp == null ? '—' : fmtPct(r.probUp * 100).replace('+', '')}</span>
              <span className="ov-num muted">{r.expMovePct == null ? '—' : `±${fmtNum(r.expMovePct, 1)}%`}</span>
              <span className={`ov-num ${r.divergence != null && r.divergence >= 0.6 ? 'warn' : ''}`}>{r.divergence == null ? '—' : fmtNum(r.divergence, 2)}</span>
              <span className="ov-ev muted small">{r.nextEvent ? `${r.nextEvent.title} · ${countdown(r.nextEvent.event_time, nowMs)}` : '—'}</span>
            </button>
          ))}
        </div>
      )}
      <p className="muted small caveat ov-divnote">
        Ordinato per “{col?.label}”. NON è una probabilità di successo: è dove condizioni e mercato divergono di più,
        cosa è più vicino, o quanto è atteso il movimento. Le prob. implicite ATM sono ~50/50 per costruzione.
      </p>
    </section>
  )
}

function SortBtn({ col, sort, setSort, num, tip }) {
  const active = sort === col.key
  return (
    <span className={num ? 'ov-num' : ''}>
      <button className={active ? 'ov-sort-active' : ''} onClick={(e) => { e.stopPropagation(); setSort(col.key) }}>
        {col.label}{active ? ' ▾' : ''}
      </button>
      {tip && <> <InfoTip text={tip.text} label={tip.label} /></>}
    </span>
  )
}

function summarise(row, nowMs) {
  const b = row.board || {}
  const hz = (b.implied?.horizons || []).filter((h) => h.available)
  const repProb = hz.filter((h) => h.prob_up != null)
  const rep = repProb.length ? repProb.reduce((a, c) => (c.days_to_expiry > a.days_to_expiry ? c : a)) : null
  const repMove = hz.length ? hz.reduce((a, c) => (c.days_to_expiry > a.days_to_expiry ? c : a)) : null
  const score = b.synthesis?.lean?.score ?? null
  const probUp = rep ? rep.prob_up : null
  // DIVERGENCE = |normalised conditions lean − signed market lean|. Market signed
  // from implied prob_up: (p−0.5)*2 (ATM≈0). Higher = bigger disagreement.
  const leanNorm = score == null ? null : Math.max(-1, Math.min(1, score / 100))
  const mktSigned = probUp == null ? null : (probUp - 0.5) * 2
  const divergence = leanNorm == null || mktSigned == null ? null : Math.abs(leanNorm - mktSigned)
  const nextEvent = (b.events && b.events[0]) || null
  const evDays = nextEvent ? (new Date(nextEvent.event_time).getTime() - nowMs) / 86_400_000 : null
  return {
    symbol: row.symbol, name: row.name || row.symbol, last: b.last ?? null,
    score, probUp, expMovePct: repMove ? repMove.expected_move_pct : null,
    divergence, nextEvent, evDays,
  }
}

function sortRows(rows, key) {
  const v = {
    div: (r) => r.divergence ?? -Infinity,
    expmove: (r) => r.expMovePct ?? -Infinity,
    lean: (r) => (r.score == null ? -Infinity : Math.abs(r.score)),
    event: (r) => (r.evDays == null ? Infinity : r.evDays), // soonest first (asc)
  }[key]
  const asc = key === 'event'
  return [...rows].sort((a, b) => (asc ? v(a) - v(b) : v(b) - v(a)))
}

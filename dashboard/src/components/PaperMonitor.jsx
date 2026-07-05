import { useEffect, useMemo, useState } from 'react'
import { insertPosition, insertJournalEntry, updatePosition, updateJournalByPosition, fetchPrices } from '../api/data'
import { positionSize, evaluatePosition } from '../lib/risk'
import { evaluateGate } from '../lib/gate'
import { committedInWindows, exitGuideFromBars } from '../lib/discipline'
import { capsFromSettings, gateInputsForSymbol, BudgetStrip, GateWarnings } from './GateShared'
import { fmtNum, fmtPct, relativeTime } from '../lib/format'

const todayISO = () => new Date().toISOString().slice(0, 10)

// Build the entry-conditions snapshot from a decision-board board (lean + implied).
export function conditionsFromBoard(board) {
  if (!board) return null
  const lean = board.synthesis?.lean || {}
  const hz = (board.implied?.horizons || []).filter((h) => h.available && h.prob_up != null)
  const rep = hz.length ? hz.reduce((a, c) => (c.days_to_expiry > a.days_to_expiry ? c : a)) : null
  return {
    captured_at: new Date().toISOString(),
    lean_score: lean.score ?? null,
    lean_label: lean.label ?? null,
    lean_direction: lean.direction ?? null,
    implied_prob_up: rep ? rep.prob_up : null,
    implied_horizon_days: rep ? rep.target_days : null,
  }
}

// "Monitora come test" — opens a HYPOTHETICAL position (paper=true). Never an
// order. Saves the entry-conditions snapshot + a linked journal draft.
export function MonitorTestForm({ symbol, instruments, settings, multiplier = 1, multiplierBySymbol,
  board, positions, closedPositions, events, priceBySymbol, conditions, onSaved }) {
  const [open, setOpen] = useState(false)
  const [f, setF] = useState({ side: 'long', entry: '', stop: '', target: '', size: '', riskPct: '', thesis: '', alignment: 'na' })
  const [status, setStatus] = useState(null)
  const [saving, setSaving] = useState(false)
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }))

  const accountSize = Number(settings?.account_size) || 0
  const maxRisk = Number(settings?.max_risk_per_trade_pct ?? 1)
  const entry = Number(f.entry)
  const stop = f.stop === '' ? null : Number(f.stop)
  const size = Number(f.size)
  const lean = board?.synthesis?.lean?.direction || null

  // Same discipline gate as the checklist, fed from the board + your positions.
  const caps = useMemo(() => capsFromSettings(settings), [settings])
  const budgetUsed = useMemo(() => committedInWindows(positions, multiplierBySymbol), [positions, multiplierBySymbol])
  const disc = useMemo(() => gateInputsForSymbol({
    symbol, technicals: board?.technicals, positions, closedPositions,
    current: priceBySymbol?.[symbol], multiplier,
  }), [symbol, board, positions, closedPositions, priceBySymbol, multiplier])

  const gate = useMemo(() => evaluateGate({
    symbol, side: f.side, entry, stop, target: f.target === '' ? null : Number(f.target), size, multiplier,
    accountSize, maxRiskPerTradePct: maxRisk,
    maxPortfolioHeatPct: Number(settings?.max_portfolio_heat_pct ?? 6),
    maxConcurrentPositions: Number(settings?.max_concurrent_positions ?? 8),
    rrMin: Number(settings?.rr_min ?? 1.5), openCount: (positions || []).length,
    thesis: f.thesis, alignment: f.alignment, leanDirection: lean,
    events: events || board?.events || [], eventWarnHours: Number(settings?.event_warn_hours ?? 48),
    requireThesis: true, atr: disc.atr, stopAtrMinMultiple: Number(settings?.stop_atr_min_multiple ?? 1.5),
    technicals: disc.technicals, recentClosedSameSymbol: disc.recentClosedSameSymbol,
    openSameSymbol: disc.openSameSymbol, budgetCaps: caps, budgetUsed,
  }), [f, entry, stop, size, multiplier, accountSize, maxRisk, settings, positions, lean, events, board, disc, caps, budgetUsed])

  function suggestAlignment() {
    if (!lean) return
    const dir = f.side === 'long' ? 'bullish' : 'bearish'
    set('alignment', lean === 'neutral' ? 'na' : (lean === dir ? 'aligned' : 'contrarian'))
  }

  function calcSize() {
    const s = positionSize(accountSize, Number(f.riskPct) || maxRisk, entry, stop, multiplier)
    if (s != null) set('size', String(Number(s.toFixed(4))))
  }

  async function save(e) {
    e.preventDefault()
    if (!(entry > 0)) return setStatus({ type: 'error', msg: 'Entry deve essere > 0.' })
    if (stop == null) return setStatus({ type: 'error', msg: 'Stop loss obbligatorio: senza stop non si registra.' })
    if (!(size > 0)) return setStatus({ type: 'error', msg: 'Size deve essere > 0.' })
    setSaving(true); setStatus(null)
    const ignored = gate.warnings.filter((w) => w.severity !== 'info').map((w) => w.code)
    const inst = instruments?.find((i) => i.symbol === symbol)
    const { data: pos, error } = await insertPosition({
      instrument_id: inst?.id ?? null, symbol, side: f.side, size,
      entry, stop, target: f.target === '' ? null : Number(f.target),
      broker: 'TEST', thesis: f.thesis || 'Posizione di test (paper).', status: 'open',
      paper: true, entry_conditions: { ...(conditions || {}), warnings: ignored, alignment: f.alignment },
    })
    if (error) { setSaving(false); return setStatus({ type: 'error', msg: error.message }) }
    const cond = conditions
      ? `Condizioni all'ingresso — lean ${cond_n(conditions.lean_score)} (${conditions.lean_label || '—'}), prob. implicita salita ${conditions.implied_prob_up != null ? fmtPct(conditions.implied_prob_up * 100).replace('+', '') : '—'}.`
      : ''
    const warnNote = ignored.length ? ` Warning: ${ignored.join(', ')}.` : ''
    await insertJournalEntry({
      position_id: pos?.id ?? null, symbol, thesis: f.thesis || 'Test (paper) da decision board.',
      entry_price: entry, stop, size,
      notes: `TEST · ${f.side} · nessun ordine reale. ${cond}${warnNote}`.trim(), reviewed: false, entry_date: todayISO(),
    })
    setSaving(false)
    setStatus({ type: 'ok', msg: 'Posizione TEST aperta (nessun ordine).' })
    setF({ side: 'long', entry: '', stop: '', target: '', size: '', riskPct: '', thesis: '', alignment: 'na' })
    setOpen(false)
    onSaved?.()
  }

  if (!open) {
    return (
      <button className="ghost small" onClick={() => setOpen(true)} title="Apre una posizione ipotetica monitorata — nessun ordine">
        🧪 Monitora come test
      </button>
    )
  }
  const m = gate.metrics
  return (
    <form className="paper-form" onSubmit={save}>
      <div className="paper-badge">TEST · nessun ordine reale · stesse guardie del gate</div>
      <BudgetStrip caps={caps} used={budgetUsed} />
      <div className="paper-fields">
        <label>Side
          <select value={f.side} onChange={(e) => set('side', e.target.value)}>
            <option value="long">long</option><option value="short">short</option>
          </select></label>
        <label>Entry<input type="number" step="any" value={f.entry} onChange={(e) => set('entry', e.target.value)} /></label>
        <label>Stop (obblig.)<input type="number" step="any" value={f.stop} onChange={(e) => set('stop', e.target.value)} /></label>
        <label>Target<input type="number" step="any" value={f.target} onChange={(e) => set('target', e.target.value)} /></label>
        <label>Rischio %<input type="number" step="any" placeholder={String(maxRisk)} value={f.riskPct} onChange={(e) => set('riskPct', e.target.value)} /></label>
        <label>Size
          <span className="size-row">
            <input type="number" step="any" value={f.size} onChange={(e) => set('size', e.target.value)} />
            <button type="button" className="ghost small" onClick={calcSize} disabled={!(entry > 0) || stop == null}>calcola</button>
          </span></label>
        <label className="full">Perché (tesi)
          <textarea rows="2" value={f.thesis} onChange={(e) => set('thesis', e.target.value)} placeholder="Ragione valida + direzione attesa nel periodo" />
        </label>
        <label>Con o contro la marea
          <span className="size-row">
            <select value={f.alignment} onChange={(e) => set('alignment', e.target.value)}>
              <option value="na">n.d.</option><option value="aligned">allineato</option><option value="contrarian">contrarian</option>
            </select>
            {lean && <button type="button" className="ghost small" onClick={suggestAlignment}>auto</button>}
          </span>
        </label>
      </div>
      {m.atr != null && entry > 0 && (
        <p className="muted small">ATR {fmtNum(m.atr, 2)} · stop consigliato ≥ {fmtNum(m.suggestedStopDistance, 2)} dal prezzo (dai spazio al movimento).</p>
      )}
      <GateWarnings warnings={size > 0 ? gate.warnings : gate.warnings.filter((w) => w.severity !== 'info')} okWhenEmpty={size > 0} />
      <div className="form-actions">
        <button type="submit" className="primary" disabled={saving || stop == null}>{saving ? 'Salvo…' : 'Apri posizione TEST'}</button>
        <button type="button" className="ghost" onClick={() => setOpen(false)}>annulla</button>
        {status && <span className={status.type === 'ok' ? 'ok' : 'error'}>{status.msg}</span>}
      </div>
      <p className="muted small">Ipotetica: serve a misurare cosa funziona (track record), non invia nulla. Gli avvisi sono advisory; lo stop è obbligatorio.</p>
    </form>
  )
}

function cond_n(v) { return v == null ? '—' : `${v > 0 ? '+' : ''}${Math.round(v)}` }

// Live cards for paper positions — the LEVELS you set (entry/stop/target/size),
// when it was opened, the current price, P&L and distances. Updates as prices /
// the clock refresh. Separate from real risk (not in heat). Close records outcome.
export function PaperPositions({ positions, priceBySymbol, multiplierBySymbol, nowMs, onChanged }) {
  // Price bars since entry -> the 2/3 profit-giveback exit guide (peak tracking).
  const [barsByInst, setBarsByInst] = useState({})
  useEffect(() => {
    const ids = [...new Set((positions || []).map((p) => p.instrument_id).filter(Boolean))]
    let cancelled = false
    Promise.all(ids.map((id) => fetchPrices(id, 250).then(({ data }) => [id, data || []])))
      .then((pairs) => { if (!cancelled) setBarsByInst(Object.fromEntries(pairs)) })
    return () => { cancelled = true }
  }, [positions])

  const cards = useMemo(() => (positions || []).map((p) => {
    const cur = priceBySymbol?.[p.symbol] ?? null
    const mult = multiplierBySymbol?.[p.symbol] ?? 1
    const e = evaluatePosition(p, { current: cur, multiplier: mult, accountSize: 0, maxRiskPerTradePct: 0, warnDays: 3, nowMs })
    const distStop = cur != null && p.stop != null ? (cur - p.stop) / cur * 100 : null
    const distTgt = cur != null && p.target != null ? (p.target - cur) / cur * 100 : null
    const pnlPct = cur != null && p.entry ? (cur / p.entry - 1) * 100 * (p.side === 'long' ? 1 : -1) : null
    const bars = barsByInst[p.instrument_id]
    const exit = bars ? exitGuideFromBars(p, bars, cur, mult) : null
    return { p, cur, mult, e, distStop, distTgt, pnlPct, exit }
  }), [positions, priceBySymbol, multiplierBySymbol, nowMs, barsByInst])

  if (!positions || positions.length === 0) {
    return <p className="muted small">Nessuna posizione di test. Aprine una da “Monitora come test”.</p>
  }

  async function close(p, cur, mult) {
    const pnl = cur != null ? (cur - p.entry) * p.size * (p.side === 'long' ? 1 : -1) * mult : null
    const outcome = pnl == null ? null : pnl > 0 ? 'win' : pnl < 0 ? 'loss' : 'breakeven'
    await updatePosition(p.id, { status: 'closed', closed_at: new Date().toISOString(), realized_pnl: pnl })
    if (p.id) await updateJournalByPosition(p.id, { exit_price: cur, pnl, outcome })
    onChanged?.()
  }

  return (
    <div className="paper-cards">
      {cards.map(({ p, cur, mult, e, distStop, distTgt, pnlPct, exit }) => (
        <article key={p.id} className="paper-card">
          <div className="paper-card-head">
            <span className="sym">{p.symbol}</span>
            <span className={`badge ${p.side}`}>{p.side}</span>
            <span className="flag-badge warn">TEST</span>
            <span className="muted small">aperta {p.opened_at ? relativeTime(p.opened_at, nowMs) : '—'}</span>
            <button className="ghost small" onClick={() => close(p, cur, mult)}>chiudi</button>
          </div>
          <div className="stat-grid">
            <Cell label="Entry" value={fmtNum(p.entry, 2)} />
            <Cell label="Stop" value={p.stop == null ? '—' : fmtNum(p.stop, 2)} />
            <Cell label="Target" value={p.target == null ? '—' : fmtNum(p.target, 2)} />
            <Cell label="Size" value={fmtNum(p.size, 2)} />
            <Cell label="Prezzo ora" value={cur == null ? '—' : fmtNum(cur, 2)} />
            <Cell label="P&L" value={e.pnl == null ? '—' : `${fmtNum(e.pnl, 0)}${pnlPct == null ? '' : ` (${fmtPct(pnlPct)})`}`}
              cls={e.pnl == null ? '' : e.pnl >= 0 ? 'pos' : 'neg'} />
            <Cell label="vs Stop" value={distStop == null ? '—' : `${fmtNum(distStop, 1)}%`} />
            <Cell label="vs Target" value={distTgt == null ? '—' : `${fmtNum(distTgt, 1)}%`} />
            <Cell label="Giorni" value={e.daysToDeadline == null ? '—' : `${e.daysToDeadline}d`} cls={e.deadlineNear ? 'warn' : ''} />
            <Cell label="R/R" value={e.rMultiple == null ? '—' : `${e.rMultiple.toFixed(1)}R`} />
          </div>
          {exit?.triggered && (
            <p className="gate-line gate-warn">
              <span className="gate-tag">⚠ 2/3</span> Profitto sceso sotto la soglia 2/3 del picco ({fmtNum(exit.peakPnl, 0)} → soglia {fmtNum(exit.thresholdPnl, 0)}, ora {fmtNum(exit.currentPnl, 0)}): valuta di prendere — guida sulla TUA regola, non una previsione.
            </p>
          )}
          {(p.entry_conditions || e.stopBreached) && (
            <p className="muted small">
              {e.stopBreached && <span className="neg">⚠ stop superato · </span>}
              {p.entry_conditions?.lean_label && `Condizioni all'ingresso: lean ${cond_n(p.entry_conditions.lean_score)} (${p.entry_conditions.lean_label})`}
              {p.entry_conditions?.implied_prob_up != null && ` · prob. implicita salita ${fmtPct(p.entry_conditions.implied_prob_up * 100).replace('+', '')}`}
              {p.entry_conditions?.warnings?.length > 0 && ` · warning all'apertura: ${p.entry_conditions.warnings.join(', ')}`}
            </p>
          )}
        </article>
      ))}
      <p className="muted small caveat">Posizioni IPOTETICHE (paper) — non inviano ordini e non contano nel rischio/heat reale. Si aggiornano col prezzo.</p>
    </div>
  )
}

function Cell({ label, value, cls = '' }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className={`stat-value ${cls}`}>{value}</span>
    </div>
  )
}

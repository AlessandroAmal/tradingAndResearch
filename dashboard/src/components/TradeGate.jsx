import { useEffect, useMemo, useState } from 'react'
import { insertPosition, insertJournalEntry, fetchDecisionBoard } from '../api/data'
import { positionSize, evaluatePosition } from '../lib/risk'
import { evaluateGate, GATE_CAVEAT } from '../lib/gate'
import { committedInWindows, setAsideToday } from '../lib/discipline'
import { BudgetStrip, GateWarnings, capsFromSettings, gateInputsForSymbol, killswitchInputs } from './GateShared'
import { fmtNum, fmtPct } from '../lib/format'
import InfoTip from './InfoTip'
import { RISK_HELP_BY_KEY as RH } from '../data/guide'

const MAX_DEADLINE_DAYS = 21
const todayISO = () => new Date().toISOString().slice(0, 10)
const maxDeadlineISO = () => {
  const d = new Date(); d.setDate(d.getDate() + MAX_DEADLINE_DAYS)
  return d.toISOString().slice(0, 10)
}

const EMPTY = {
  symbol: '', side: 'long', size: '', entry: '', stop: '', target: '',
  riskPct: '', thesis: '', alignment: 'na', deadline: '', broker: '',
}

// Pre-trade gate — checklist that VALIDATES numbers against your rules and warns
// (never blocks, read-only), then records the position + a linked journal draft.
export default function TradeGate({ instruments, settings, positions, closedPositions, priceBySymbol, multiplierBySymbol, events, defaultBroker, onSaved }) {
  const [form, setForm] = useState({ ...EMPTY, broker: defaultBroker || '' })
  const [lean, setLean] = useState(null)
  const [technicals, setTechnicals] = useState(null)
  const [status, setStatus] = useState(null)
  const [saving, setSaving] = useState(false)
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const accountSize = Number(settings?.account_size) || 0
  const maxRisk = Number(settings?.max_risk_per_trade_pct ?? 1)
  const maxHeat = Number(settings?.max_portfolio_heat_pct ?? 6)
  const maxPos = Number(settings?.max_concurrent_positions ?? 8)
  const rrMin = Number(settings?.rr_min ?? 1.5)
  const eventWarnHours = Number(settings?.event_warn_hours ?? 48)
  const stopAtrMinMultiple = Number(settings?.stop_atr_min_multiple ?? 1.5)

  const multiplier = useMemo(
    () => Number(multiplierBySymbol?.[form.symbol]) || 1,
    [multiplierBySymbol, form.symbol],
  )

  // Decision-board lean + technicals (ATR for stop-room, MAs for countertrend).
  useEffect(() => {
    if (!form.symbol) { setLean(null); setTechnicals(null); return }
    fetchDecisionBoard(form.symbol).then(({ data }) => {
      setLean(data?.board?.synthesis?.lean?.direction || null)
      setTechnicals(data?.board?.technicals || null)
    })
  }, [form.symbol])

  // Committed real risk per window + today's set-aside reminder.
  const caps = useMemo(() => capsFromSettings(settings), [settings])
  const budgetUsed = useMemo(
    () => committedInWindows(positions, multiplierBySymbol),
    [positions, multiplierBySymbol],
  )
  const setAside = useMemo(
    () => setAsideToday(closedPositions, Number(settings?.set_aside_per_day ?? 100)),
    [closedPositions, settings],
  )

  // Existing portfolio heat from open positions (with correct point value).
  const existingHeatPct = useMemo(() => {
    return (positions || []).reduce((acc, p) => {
      const ev = evaluatePosition(p, {
        current: priceBySymbol?.[p.symbol], multiplier: multiplierBySymbol?.[p.symbol] || 1,
        accountSize, maxRiskPerTradePct: maxRisk, warnDays: 3, nowMs: Date.now(),
      })
      return acc + (ev.openRiskPct || 0)
    }, 0)
  }, [positions, priceBySymbol, multiplierBySymbol, accountSize, maxRisk])

  const entry = Number(form.entry)
  const stop = form.stop === '' ? null : Number(form.stop)
  const target = form.target === '' ? null : Number(form.target)
  const size = Number(form.size)

  const disc = useMemo(() => gateInputsForSymbol({
    symbol: form.symbol, technicals, positions, closedPositions,
    current: priceBySymbol?.[form.symbol], multiplier,
  }), [form.symbol, technicals, positions, closedPositions, priceBySymbol, multiplier])

  const ks = useMemo(() => killswitchInputs({ settings, closedPositions, symbol: form.symbol, side: form.side, paper: false }), [settings, closedPositions, form.symbol, form.side])
  const gate = useMemo(() => evaluateGate({
    symbol: form.symbol, side: form.side, entry, stop, target, size, multiplier,
    accountSize, maxRiskPerTradePct: maxRisk, maxPortfolioHeatPct: maxHeat,
    maxConcurrentPositions: maxPos, rrMin, existingHeatPct, openCount: (positions || []).length,
    thesis: form.thesis, alignment: form.alignment, leanDirection: lean,
    events, eventWarnHours,
    requireThesis: true, atr: disc.atr, stopAtrMinMultiple, technicals: disc.technicals,
    recentClosedSameSymbol: disc.recentClosedSameSymbol, openSameSymbol: disc.openSameSymbol,
    budgetCaps: caps, budgetUsed, ...ks,
  }), [form, entry, stop, target, size, multiplier, accountSize, maxRisk, maxHeat, maxPos, rrMin, existingHeatPct, positions, lean, events, eventWarnHours, disc, stopAtrMinMultiple, caps, budgetUsed, ks])

  const m = gate.metrics
  const warnCount = gate.warnings.filter((w) => w.severity === 'warn').length
  const blockCount = gate.warnings.filter((w) => w.severity === 'block').length

  function calcSize() {
    const s = positionSize(accountSize, Number(form.riskPct) || maxRisk, entry, stop, multiplier)
    if (s != null) set('size', String(Number(s.toFixed(4))))
  }

  function suggestAlignment() {
    if (!lean) return
    const dir = form.side === 'long' ? 'bullish' : 'bearish'
    set('alignment', lean === 'neutral' ? 'na' : (lean === dir ? 'aligned' : 'contrarian'))
  }

  async function onConfirm(e, paper = false) {
    e.preventDefault()
    if (!form.symbol) return setStatus({ type: 'error', msg: 'Scegli uno strumento.' })
    if (!(entry > 0)) return setStatus({ type: 'error', msg: 'Entry deve essere > 0.' })
    // STOP mandatory — applies to real AND paper (no sizing/registration without it).
    if (stop == null) return setStatus({ type: 'error', msg: 'Stop loss obbligatorio: senza stop non si registra.' })
    if (!(size > 0)) return setStatus({ type: 'error', msg: 'Size deve essere > 0.' })
    if (!paper && !form.thesis.trim()) return setStatus({ type: 'error', msg: 'La tesi è obbligatoria.' })
    // Budget caps in 'block' mode stop a REAL registration (still no order — the
    // cockpit is read-only; this is YOUR guardrail). Paper is exempt (counted apart).
    if (!paper) {
      const blocker = gate.warnings.find((w) => w.severity === 'block' && w.code !== 'stop_missing')
      if (blocker) return setStatus({ type: 'error', msg: `Bloccato dalla tua regola: ${blocker.message}` })
    }

    setSaving(true); setStatus(null)
    // Warnings the user is proceeding past — recorded for the honest review.
    const ignored = gate.warnings.filter((w) => w.severity !== 'info').map((w) => w.code)
    const inst = instruments.find((i) => i.symbol === form.symbol)
    const posPayload = {
      instrument_id: inst?.id ?? null, symbol: form.symbol, side: form.side,
      size, entry, stop, target, deadline: form.deadline || null,
      broker: paper ? 'TEST' : (form.broker || null), thesis: form.thesis, status: 'open',
      paper, entry_conditions: paper ? { lean_direction: lean, alignment: form.alignment, warnings: ignored, captured_at: new Date().toISOString() } : null,
    }
    const { data: pos, error } = await insertPosition(posPayload)
    if (error) { setSaving(false); return setStatus({ type: 'error', msg: error.message }) }

    // Auto-create a linked journal draft (read-only: registration only).
    const align = { aligned: 'allineato alla marea macro', contrarian: 'contrarian (contro la marea)' }[form.alignment] || 'n.d.'
    const warnNote = ignored.length ? ` · Warning al momento dell'apertura: ${ignored.join(', ')}` : ''
    const draft = {
      position_id: pos?.id ?? null, symbol: form.symbol, thesis: form.thesis,
      entry_price: entry, stop, size,
      notes: `${paper ? 'TEST · ' : ''}${form.side} · Allineamento macro: ${align}${lean ? ` (lean: ${lean})` : ''}${warnNote}`,
      reviewed: false, entry_date: todayISO(),
    }
    const j = await insertJournalEntry(draft)
    setSaving(false)
    setStatus({ type: 'ok', msg: paper
      ? 'Posizione TEST aperta (nessun ordine) + bozza journal.'
      : (j.error ? 'Posizione salvata (bozza journal non riuscita).' : 'Posizione + bozza journal salvate.') })
    setForm({ ...EMPTY, broker: form.broker })
    onSaved?.()
  }

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Nuovo trade — checklist</h2>
        <span className="muted small">valida disciplina e rischio · nessun ordine</span>
      </header>

      <BudgetStrip caps={caps} used={budgetUsed} setAside={setAside} />

      <form className="pos-form" onSubmit={onConfirm}>
        <label>Strumento
          <select value={form.symbol} onChange={(e) => set('symbol', e.target.value)}>
            <option value="">— seleziona —</option>
            {instruments.map((i) => (
              <option key={i.id} value={i.symbol}>
                {i.symbol}{Number(i.contract_multiplier) !== 1 ? ` ·×${i.contract_multiplier}` : ''}
              </option>
            ))}
          </select>
        </label>
        <label>Side
          <select value={form.side} onChange={(e) => set('side', e.target.value)}>
            <option value="long">long</option><option value="short">short</option>
          </select>
        </label>
        <label>Entry
          <input type="number" step="any" value={form.entry} onChange={(e) => set('entry', e.target.value)} />
        </label>
        <label><span className="field-label">Stop (obbligatorio) <InfoTip text={RH.risk_per_trade.text} label={RH.risk_per_trade.label} /></span>
          <input type="number" step="any" value={form.stop} onChange={(e) => set('stop', e.target.value)} />
          {m.atr != null && entry > 0 && (
            <span className="muted small">ATR {fmtNum(m.atr, 2)} · stop consigliato ≥ {fmtNum(m.suggestedStopDistance, 2)} dal prezzo (dai spazio al movimento)</span>
          )}
        </label>
        <label>Target
          <input type="number" step="any" value={form.target} onChange={(e) => set('target', e.target.value)} />
        </label>
        <label>Rischio % (per size)
          <input type="number" step="any" placeholder={String(maxRisk)} value={form.riskPct} onChange={(e) => set('riskPct', e.target.value)} />
        </label>
        <label><span className="field-label">Size <InfoTip text={RH.position_sizing.text} label={RH.position_sizing.label} /></span>
          <div className="size-row">
            <input type="number" step="any" value={form.size} onChange={(e) => set('size', e.target.value)} />
            <button type="button" className="ghost small" onClick={calcSize} disabled={!(entry > 0) || stop == null}>calcola</button>
          </div>
        </label>
        <label>Deadline (≤3 sett.)
          <input type="date" value={form.deadline} min={todayISO()} max={maxDeadlineISO()} onChange={(e) => set('deadline', e.target.value)} />
        </label>
        <label className="full">Tesi (obbligatoria)
          <textarea rows="2" value={form.thesis} onChange={(e) => set('thesis', e.target.value)} />
        </label>
        <label>Con o contro la marea
          <div className="size-row">
            <select value={form.alignment} onChange={(e) => set('alignment', e.target.value)}>
              <option value="na">n.d.</option>
              <option value="aligned">allineato</option>
              <option value="contrarian">contrarian</option>
            </select>
            {lean && <button type="button" className="ghost small" onClick={suggestAlignment}>auto</button>}
          </div>
        </label>
        <label>Lettura macro (decision board)
          <span className={`chip ${lean ? '' : 'muted'}`}>{lean ? `lean: ${lean}` : 'n/d'}</span>
        </label>
      </form>

      {/* Numbers — computed with the correct point value */}
      <div className="stat-grid">
        <Stat label="Rischio €" value={m.riskAmount == null ? '—' : fmtNum(m.riskAmount, 0)} />
        <Stat label="Rischio % conto" tip={RH.risk_per_trade} value={m.riskPct == null ? '—' : fmtPct(m.riskPct)} cls={m.riskPct > maxRisk ? 'neg' : ''} />
        <Stat label="R/R" tip={RH.r_multiple} value={m.rr == null ? '—' : `${m.rr.toFixed(2)}R`} cls={m.rr != null && m.rr < rrMin ? 'warn' : ''} />
        <Stat label="Heat risultante" tip={RH.portfolio_heat} value={fmtPct(m.resultingHeatPct)} cls={m.resultingHeatPct > maxHeat ? 'neg' : ''} />
        <Stat label="Posizioni" tip={RH.concurrent} value={`${m.nConcurrent}/${maxPos}`} cls={m.nConcurrent > maxPos ? 'neg' : ''} />
        <Stat label="Moltiplicatore" value={`×${multiplier}`} cls={multiplier === 1 ? 'warn' : ''} />
      </div>
      {form.symbol && multiplier === 1 && (
        <p className="muted small">⚠ Point value ×1: il rischio per {form.symbol} è calcolato come 1 unità = 1 (corretto per azioni/crypto; per future/CFD imposta <code>contract_multiplier</code> in config, altrimenti il rischio è sottostimato).</p>
      )}

      {/* Warnings — colour = severity only; only stop/budget-block are blocking */}
      <GateWarnings warnings={form.symbol && (size > 0) ? gate.warnings : gate.warnings.filter((w) => w.severity !== 'info')} okWhenEmpty={!!form.symbol && size > 0} />

      <p className="muted small caveat">{GATE_CAVEAT}</p>

      <div className="form-actions">
        <button type="button" className="primary" onClick={(e) => onConfirm(e, false)} disabled={saving || blockCount > 0}>
          {saving ? 'Salvo…' : blockCount > 0 ? `Bloccato (${blockCount})` : `Conferma e registra${warnCount ? ` (${warnCount} warning)` : ''}`}
        </button>
        <button type="button" className="ghost" onClick={(e) => onConfirm(e, true)} disabled={saving || stop == null}
          title="Apre una posizione ipotetica monitorata — nessun ordine">
          🧪 Monitora come test
        </button>
        {status && <span className={status.type === 'ok' ? 'ok' : 'error'}>{status.msg}</span>}
      </div>
    </section>
  )
}

function Stat({ label, value, cls = '', tip }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}{tip && <> <InfoTip text={tip.text} label={tip.label} /></>}</span>
      <span className={`stat-value ${cls}`}>{value}</span>
    </div>
  )
}

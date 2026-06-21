import { useMemo, useState } from 'react'
import { insertPosition } from '../api/data'
import InfoTip from './InfoTip'
import { FIELD_HELP_BY_KEY } from '../data/guide'

// Field caption + inline info tooltip, sharing the Guide's texts.
function FieldLabel({ field, children }) {
  const help = FIELD_HELP_BY_KEY[field]
  return (
    <span className="field-label">
      {children}
      {help && <InfoTip text={help.text} label={help.label} />}
    </span>
  )
}

const MAX_DEADLINE_DAYS = 21 // business rule: deadline within 3 weeks

function maxDeadlineISO() {
  const d = new Date()
  d.setDate(d.getDate() + MAX_DEADLINE_DAYS)
  return d.toISOString().slice(0, 10)
}
function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

const EMPTY = {
  symbol: '', side: 'long', size: '', entry: '', stop: '', target: '',
  deadline: '', broker: '', thesis: '',
}

// Manual position-entry form (read-only cockpit: tracking only, no execution).
export default function PositionForm({ instruments, defaultBroker, onSaved }) {
  const [form, setForm] = useState({ ...EMPTY, broker: defaultBroker || '' })
  const [status, setStatus] = useState(null) // {type, msg}
  const [saving, setSaving] = useState(false)

  const maxDeadline = useMemo(maxDeadlineISO, [])

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  function validate() {
    if (!form.symbol) return 'Pick an instrument.'
    if (!form.size || Number(form.size) <= 0) return 'Size must be > 0.'
    if (!form.entry || Number(form.entry) <= 0) return 'Entry must be > 0.'
    if (form.deadline) {
      if (form.deadline > maxDeadline)
        return `Deadline must be within ${MAX_DEADLINE_DAYS} days.`
      if (form.deadline < todayISO()) return 'Deadline is in the past.'
    }
    return null
  }

  async function onSubmit(e) {
    e.preventDefault()
    const err = validate()
    if (err) {
      setStatus({ type: 'error', msg: err })
      return
    }
    setSaving(true)
    setStatus(null)
    const inst = instruments.find((i) => i.symbol === form.symbol)
    const payload = {
      instrument_id: inst?.id ?? null,
      symbol: form.symbol,
      side: form.side,
      size: Number(form.size),
      entry: Number(form.entry),
      stop: form.stop ? Number(form.stop) : null,
      target: form.target ? Number(form.target) : null,
      deadline: form.deadline || null,
      broker: form.broker || null,
      thesis: form.thesis || null,
      status: 'open',
    }
    const { error } = await insertPosition(payload)
    setSaving(false)
    if (error) {
      setStatus({ type: 'error', msg: error.message })
    } else {
      setStatus({ type: 'ok', msg: 'Position saved.' })
      setForm({ ...EMPTY, broker: form.broker })
      onSaved?.()
    }
  }

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>New position</h2>
        <span className="muted small">tracking only · no order is placed</span>
      </header>

      <form className="pos-form" onSubmit={onSubmit}>
        <label>
          <FieldLabel field="symbol">Instrument</FieldLabel>
          <select value={form.symbol} onChange={(e) => set('symbol', e.target.value)}>
            <option value="">— select —</option>
            {instruments.map((i) => (
              <option key={i.id} value={i.symbol}>
                {i.symbol} {i.name ? `· ${i.name}` : ''}
              </option>
            ))}
          </select>
        </label>

        <label>
          <FieldLabel field="side">Side</FieldLabel>
          <select value={form.side} onChange={(e) => set('side', e.target.value)}>
            <option value="long">long</option>
            <option value="short">short</option>
          </select>
        </label>

        <label>
          <FieldLabel field="size">Size</FieldLabel>
          <input type="number" step="any" min="0" value={form.size}
            onChange={(e) => set('size', e.target.value)} />
        </label>

        <label>
          <FieldLabel field="entry">Entry</FieldLabel>
          <input type="number" step="any" min="0" value={form.entry}
            onChange={(e) => set('entry', e.target.value)} />
        </label>

        <label>
          <FieldLabel field="stop">Stop</FieldLabel>
          <input type="number" step="any" min="0" value={form.stop}
            onChange={(e) => set('stop', e.target.value)} />
        </label>

        <label>
          <FieldLabel field="target">Target</FieldLabel>
          <input type="number" step="any" min="0" value={form.target}
            onChange={(e) => set('target', e.target.value)} />
        </label>

        <label>
          <FieldLabel field="deadline">Deadline (≤ 3 weeks)</FieldLabel>
          <input type="date" value={form.deadline} min={todayISO()} max={maxDeadline}
            onChange={(e) => set('deadline', e.target.value)} />
        </label>

        <label>
          <FieldLabel field="broker">Broker</FieldLabel>
          <input type="text" value={form.broker}
            onChange={(e) => set('broker', e.target.value)} />
        </label>

        <label className="full">
          <FieldLabel field="thesis">Thesis</FieldLabel>
          <textarea rows="3" value={form.thesis}
            onChange={(e) => set('thesis', e.target.value)} />
        </label>

        <div className="full form-actions">
          <button type="submit" disabled={saving}>
            {saving ? 'Saving…' : 'Save position'}
          </button>
          {status && (
            <span className={status.type === 'ok' ? 'ok' : 'error'}>{status.msg}</span>
          )}
        </div>
      </form>
    </section>
  )
}

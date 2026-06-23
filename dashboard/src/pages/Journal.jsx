import { useCallback, useEffect, useState } from 'react'
import {
  fetchJournalEntries,
  insertJournalEntry,
  updateJournalEntry,
  fetchLatestBriefing,
} from '../api/data'
import { fmtNum } from '../lib/format'

const EMPTY = {
  symbol: '', position_id: '', thesis: '', entry_price: '', exit_price: '',
  size: '', stop: '', outcome: '', pnl: '', thesis_played_out: '', notes: '',
  reviewed: false,
}

// tri-state select <-> boolean|null
const TPO = { '': null, yes: true, no: false }
const TPO_REV = new Map([[true, 'yes'], [false, 'no']])

// "Journal" view: add/edit entries (optional position link with pre-fill),
// plus the latest AI review. Read-only cockpit — records trades, never trades.
export default function Journal({ instruments, positions }) {
  const [entries, setEntries] = useState([])
  const [review, setReview] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [editingId, setEditingId] = useState(null)
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    const [e, r] = await Promise.all([
      fetchJournalEntries(200),
      fetchLatestBriefing('journal_review'),
    ])
    if (e.error) setError(e.error.message)
    setEntries(e.data || [])
    setReview(r.data || null)
  }, [])

  useEffect(() => { load() }, [load])

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  // Pre-fill from a linked open position.
  function onLinkPosition(positionId) {
    const p = positions.find((x) => x.id === positionId)
    setForm((f) => ({
      ...f,
      position_id: positionId,
      ...(p && {
        symbol: p.symbol ?? f.symbol,
        entry_price: p.entry ?? f.entry_price,
        size: p.size ?? f.size,
        stop: p.stop ?? f.stop,
        thesis: p.thesis ?? f.thesis,
      }),
    }))
  }

  function startEdit(e) {
    setEditingId(e.id)
    setForm({
      symbol: e.symbol ?? '', position_id: e.position_id ?? '',
      thesis: e.thesis ?? '', entry_price: e.entry_price ?? '',
      exit_price: e.exit_price ?? '', size: e.size ?? '', stop: e.stop ?? '',
      outcome: e.outcome ?? '', pnl: e.pnl ?? '',
      thesis_played_out: TPO_REV.get(e.thesis_played_out) ?? '',
      notes: e.notes ?? '', reviewed: !!e.reviewed,
    })
    setStatus(null)
  }

  function resetForm() {
    setEditingId(null)
    setForm(EMPTY)
    setStatus(null)
  }

  const num = (v) => (v === '' || v == null ? null : Number(v))

  async function onSubmit(ev) {
    ev.preventDefault()
    if (!form.symbol) { setStatus({ type: 'error', msg: 'Pick an instrument.' }); return }
    setSaving(true)
    setStatus(null)
    const payload = {
      symbol: form.symbol,
      position_id: form.position_id || null,
      thesis: form.thesis || null,
      entry_price: num(form.entry_price),
      exit_price: num(form.exit_price),
      size: num(form.size),
      stop: num(form.stop),
      outcome: form.outcome || null,
      pnl: num(form.pnl),
      thesis_played_out: TPO[form.thesis_played_out],
      notes: form.notes || null,
      reviewed: !!form.reviewed,
    }
    const res = editingId
      ? await updateJournalEntry(editingId, payload)
      : await insertJournalEntry(payload)
    setSaving(false)
    if (res.error) {
      setStatus({ type: 'error', msg: res.error.message })
    } else {
      setStatus({ type: 'ok', msg: editingId ? 'Entry updated.' : 'Entry saved.' })
      resetForm()
      load()
    }
  }

  return (
    <div className="journal">
      <section className="panel">
        <header className="panel-head">
          <h2>{editingId ? 'Edit journal entry' : 'New journal entry'}</h2>
          <span className="muted small">records a trade · places nothing</span>
        </header>

        <form className="pos-form" onSubmit={onSubmit}>
          <label>
            Instrument
            <select value={form.symbol} onChange={(e) => set('symbol', e.target.value)}>
              <option value="">— select —</option>
              {instruments.map((i) => (
                <option key={i.id} value={i.symbol}>{i.symbol}</option>
              ))}
            </select>
          </label>
          <label>
            Link position (pre-fills)
            <select value={form.position_id} onChange={(e) => onLinkPosition(e.target.value)}>
              <option value="">— none —</option>
              {positions.map((p) => (
                <option key={p.id} value={p.id}>{p.symbol} · {p.side} @ {p.entry}</option>
              ))}
            </select>
          </label>
          <label>Entry price
            <input type="number" step="any" value={form.entry_price}
              onChange={(e) => set('entry_price', e.target.value)} /></label>
          <label>Exit price
            <input type="number" step="any" value={form.exit_price}
              onChange={(e) => set('exit_price', e.target.value)} /></label>
          <label>Size
            <input type="number" step="any" value={form.size}
              onChange={(e) => set('size', e.target.value)} /></label>
          <label>Stop
            <input type="number" step="any" value={form.stop}
              onChange={(e) => set('stop', e.target.value)} /></label>
          <label>Outcome
            <select value={form.outcome} onChange={(e) => set('outcome', e.target.value)}>
              <option value="">— open —</option>
              <option value="win">win</option>
              <option value="loss">loss</option>
              <option value="breakeven">breakeven</option>
            </select></label>
          <label>P&amp;L
            <input type="number" step="any" value={form.pnl}
              onChange={(e) => set('pnl', e.target.value)} /></label>
          <label>Thesis played out?
            <select value={form.thesis_played_out}
              onChange={(e) => set('thesis_played_out', e.target.value)}>
              <option value="">— n/a —</option>
              <option value="yes">yes</option>
              <option value="no">no</option>
            </select></label>
          <label className="chk">
            <input type="checkbox" checked={form.reviewed}
              onChange={(e) => set('reviewed', e.target.checked)} /> Reviewed
          </label>
          <label className="full">Thesis
            <textarea rows="2" value={form.thesis}
              onChange={(e) => set('thesis', e.target.value)} /></label>
          <label className="full">Notes
            <textarea rows="2" value={form.notes}
              onChange={(e) => set('notes', e.target.value)} /></label>

          <div className="full form-actions">
            <button type="submit" disabled={saving}>
              {saving ? 'Saving…' : editingId ? 'Update entry' : 'Save entry'}
            </button>
            {editingId && (
              <button type="button" className="ghost" onClick={resetForm}>Cancel</button>
            )}
            {status && (
              <span className={status.type === 'ok' ? 'ok' : 'error'}>{status.msg}</span>
            )}
          </div>
        </form>
      </section>

      <section className="panel">
        <header className="panel-head"><h2>Entries</h2></header>
        {error && <p className="error">Journal unavailable — {error}</p>}
        {entries.length === 0 && !error && <p className="muted small">No entries yet.</p>}
        <ul className="journal-list">
          {entries.map((e) => (
            <li key={e.id} className="journal-row">
              <div className="journal-main">
                <span className="sym">{e.symbol}</span>
                {e.outcome && (
                  <span className={`flag-badge ${e.outcome === 'loss' ? 'bad' : ''}`}>{e.outcome}</span>
                )}
                {e.pnl != null && (
                  <span className={e.pnl >= 0 ? 'pos' : 'neg'}>{fmtNum(e.pnl, 0)}</span>
                )}
                <span className="muted small">{e.entry_date}</span>
                <button type="button" className="ghost small" onClick={() => startEdit(e)}>edit</button>
              </div>
              {e.thesis && <div className="muted small">{e.thesis}</div>}
            </li>
          ))}
        </ul>
      </section>

      <section className="panel">
        <header className="panel-head">
          <h2>AI review</h2>
          {review?.generated_at && (
            <span className="muted small">{new Date(review.generated_at).toLocaleString()}</span>
          )}
        </header>
        {!review && (
          <p className="muted small">
            No review yet. Run <code>python -m app.main journal-review</code> in the worker.
          </p>
        )}
        {review && (
          <>
            <pre className="briefing-body">{review.body}</pre>
            {review.uncertainty_note && (
              <p className="briefing-caveat">⚠ {review.uncertainty_note}</p>
            )}
            <p className="muted small">
              To refresh: run <code>python -m app.main journal-review</code> in the worker.
            </p>
          </>
        )}
      </section>
    </div>
  )
}

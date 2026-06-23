import { useCallback, useEffect, useState } from 'react'
import {
  fetchAlertRules,
  insertAlertRule,
  updateAlertRule,
  deleteAlertRule,
  fetchAlertsLog,
} from '../api/data'

// "Alert" view: standing-category toggles, user-defined price/IV thresholds,
// and the sent-alerts history. Read-only cockpit — alerts NOTIFY, never trade.
// Rules are stored in alert_rules; the worker evaluates and dispatches.
export default function Alerts({ instruments }) {
  const [rules, setRules] = useState([])
  const [log, setLog] = useState([])
  const [error, setError] = useState(null)
  const [form, setForm] = useState({ kind: 'price', symbol: '', op: 'above', threshold: '' })
  const [status, setStatus] = useState(null)

  const load = useCallback(async () => {
    const [r, l] = await Promise.all([fetchAlertRules(), fetchAlertsLog(40)])
    if (r.error) setError(r.error.message)
    setRules(r.data || [])
    setLog(l.data || [])
  }, [])
  useEffect(() => { load() }, [load])

  const standing = rules.filter((r) => r.kind === 'standing')
  const userRules = rules.filter((r) => r.kind === 'price' || r.kind === 'iv')

  async function toggle(rule) {
    await updateAlertRule(rule.id, { enabled: !rule.enabled })
    load()
  }

  async function addRule(e) {
    e.preventDefault()
    if (!form.symbol || form.threshold === '') {
      setStatus({ type: 'error', msg: 'Scegli strumento e soglia.' })
      return
    }
    const label = `${form.symbol} ${form.kind === 'iv' ? 'IV' : 'prezzo'} ${form.op === 'above' ? '≥' : '≤'} ${form.threshold}`
    const { error } = await insertAlertRule({
      kind: form.kind, symbol: form.symbol, op: form.op,
      threshold: Number(form.threshold), label, enabled: true,
    })
    if (error) setStatus({ type: 'error', msg: error.message })
    else {
      setStatus({ type: 'ok', msg: 'Regola creata.' })
      setForm({ kind: 'price', symbol: '', op: 'above', threshold: '' })
      load()
    }
  }

  async function removeRule(id) {
    await deleteAlertRule(id)
    load()
  }

  return (
    <div className="journal">
      {error && <p className="error">Alert non disponibili — {error} (applica la 0010 + seed)</p>}

      <section className="panel">
        <header className="panel-head"><h2>Alert standing</h2></header>
        {standing.length === 0 && <p className="muted small">Nessuna regola standing. Esegui il seed del worker.</p>}
        <ul className="journal-list">
          {standing.map((r) => (
            <li key={r.id} className="journal-row journal-main">
              <label className="chk-inline">
                <input type="checkbox" checked={!!r.enabled} onChange={() => toggle(r)} />
                {r.label || r.standing_type}
              </label>
            </li>
          ))}
        </ul>
      </section>

      <section className="panel">
        <header className="panel-head">
          <h2>Soglie personalizzate</h2>
          <span className="muted small">prezzo / IV su uno strumento</span>
        </header>
        <form className="pos-form" onSubmit={addRule}>
          <label>Tipo
            <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
              <option value="price">prezzo</option>
              <option value="iv">IV</option>
            </select>
          </label>
          <label>Strumento
            <select value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value })}>
              <option value="">— scegli —</option>
              {instruments.map((i) => <option key={i.id} value={i.symbol}>{i.symbol}</option>)}
            </select>
          </label>
          <label>Condizione
            <select value={form.op} onChange={(e) => setForm({ ...form, op: e.target.value })}>
              <option value="above">sopra / ≥</option>
              <option value="below">sotto / ≤</option>
            </select>
          </label>
          <label>Soglia
            <input type="number" step="any" value={form.threshold}
              onChange={(e) => setForm({ ...form, threshold: e.target.value })} />
          </label>
          <div className="full form-actions">
            <button type="submit">Crea regola</button>
            {status && <span className={status.type === 'ok' ? 'ok' : 'error'}>{status.msg}</span>}
          </div>
        </form>

        <ul className="journal-list">
          {userRules.map((r) => (
            <li key={r.id} className="journal-row journal-main">
              <label className="chk-inline">
                <input type="checkbox" checked={!!r.enabled} onChange={() => toggle(r)} />
                <span className="sym">{r.symbol}</span>
                <span className="muted small">
                  {r.kind === 'iv' ? 'IV' : 'prezzo'} {r.op === 'above' ? '≥' : '≤'} {r.threshold}
                </span>
              </label>
              <button type="button" className="ghost small" onClick={() => removeRule(r.id)}>elimina</button>
            </li>
          ))}
        </ul>
      </section>

      <section className="panel">
        <header className="panel-head"><h2>Storico alert</h2></header>
        {log.length === 0 && <p className="muted small">Nessun alert inviato ancora.</p>}
        <ul className="journal-list">
          {log.map((a) => (
            <li key={a.id} className="journal-row">
              <div className="journal-main">
                <span className={`flag-badge ${a.severity === 'critical' || a.severity === 'warning' ? 'bad' : ''}`}>
                  {a.severity}
                </span>
                <span>{a.message}</span>
                <span className={`pill ${a.delivered ? '' : 'pill-gauge'}`}>
                  {a.delivered ? 'inviato' : 'non inviato'}
                </span>
                <span className="muted small">{a.triggered_at ? new Date(a.triggered_at).toLocaleString() : ''}</span>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

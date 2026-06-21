import { useMemo, useState } from 'react'
import { positionSize, openRisk, pctOfAccount, rMultiple } from '../lib/risk'
import { fmtNum, fmtPct } from '../lib/format'
import InfoTip from './InfoTip'

// Position-sizing calculator: entry/stop/risk% [+ instrument] -> size.
// Pure read-only math — it suggests a size, it does NOT place anything.
export default function SizingCalculator({ instruments, settings }) {
  const accountFromSettings = Number(settings?.account_size) || 0
  const defaultRisk = settings?.max_risk_per_trade_pct ?? 1

  const [symbol, setSymbol] = useState('')
  const [account, setAccount] = useState(accountFromSettings ? String(accountFromSettings) : '')
  const [riskPct, setRiskPct] = useState(String(defaultRisk))
  const [entry, setEntry] = useState('')
  const [stop, setStop] = useState('')
  const [target, setTarget] = useState('')

  const multiplier = useMemo(() => {
    const inst = instruments.find((i) => i.symbol === symbol)
    return Number(inst?.contract_multiplier) || 1
  }, [instruments, symbol])

  const acct = Number(account) || accountFromSettings
  const r = Number(riskPct)
  const e = Number(entry)
  const s = stop === '' ? null : Number(stop)
  const t = target === '' ? null : Number(target)

  const size = positionSize(acct, r, e, s, multiplier)
  const risk = size != null ? openRisk(e, s, size, multiplier) : null
  const riskPctOfAcct = pctOfAccount(risk, acct)
  const rr = rMultiple(e, s, t)

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Sizing calculator</h2>
        <span className="muted small">suggests a size · places nothing</span>
      </header>

      <form className="pos-form" onSubmit={(ev) => ev.preventDefault()}>
        <label>
          <span className="field-label">Instrument <InfoTip text="Optional — sets the contract multiplier / point value for futures/CFD/FX." label="Instrument" /></span>
          <select value={symbol} onChange={(ev) => setSymbol(ev.target.value)}>
            <option value="">— generic (×1) —</option>
            {instruments.map((i) => (
              <option key={i.id} value={i.symbol}>
                {i.symbol}{Number(i.contract_multiplier) !== 1 ? ` ·×${i.contract_multiplier}` : ''}
              </option>
            ))}
          </select>
        </label>
        <label>
          Account
          <input type="number" step="any" min="0" value={account}
            onChange={(ev) => setAccount(ev.target.value)} />
        </label>
        <label>
          Risk %
          <input type="number" step="any" min="0" value={riskPct}
            onChange={(ev) => setRiskPct(ev.target.value)} />
        </label>
        <label>
          Entry
          <input type="number" step="any" value={entry}
            onChange={(ev) => setEntry(ev.target.value)} />
        </label>
        <label>
          Stop
          <input type="number" step="any" value={stop}
            onChange={(ev) => setStop(ev.target.value)} />
        </label>
        <label>
          Target
          <input type="number" step="any" value={target}
            onChange={(ev) => setTarget(ev.target.value)} />
        </label>
      </form>

      <div className="stat-grid">
        <Stat label="Suggested size" value={size == null ? '—' : fmtNum(size, 2)} big />
        <Stat label="Open risk" value={risk == null ? '—' : fmtNum(risk, 0)} />
        <Stat label="Risk % acct" value={riskPctOfAcct == null ? '—' : fmtPct(riskPctOfAcct)} />
        <Stat label="R:R (target)" value={rr == null ? '—' : `${rr.toFixed(2)}R`} />
      </div>
    </section>
  )
}

function Stat({ label, value, big }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className={`stat-value ${big ? 'accent' : ''}`}>{value}</span>
    </div>
  )
}

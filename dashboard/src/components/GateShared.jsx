// Shared pieces for the discipline gate, used by BOTH the "Nuovo trade" checklist
// and the paper "Monitora come test" form, so the guards fire identically in both.
// READ-ONLY: renders warnings and budget context; never places an order.
import { unrealizedPnl } from '../lib/risk'
import { fmtNum } from '../lib/format'

// risk_settings singleton -> budget caps for the gate.
export function capsFromSettings(s) {
  const num = (v, d) => (v == null ? d : Number(v))
  return {
    day: { max: num(s?.budget_day, 100), mode: s?.budget_day_mode || 'warn' },
    week: { max: num(s?.budget_week, 175), mode: s?.budget_week_mode || 'warn' },
    month: { max: num(s?.budget_month, 300), mode: s?.budget_month_mode || 'warn' },
  }
}

// Per-symbol discipline inputs (ATR + trend technicals + same-symbol trades).
export function gateInputsForSymbol({ symbol, technicals, positions, closedPositions, current, multiplier }) {
  const t = technicals || null
  const openSameSymbol = (positions || [])
    .filter((p) => p.symbol === symbol && !p.paper)
    .map((p) => ({ side: p.side, pnl: unrealizedPnl(current, Number(p.entry), Number(p.size), p.side, multiplier) }))
  const recentClosedSameSymbol = (closedPositions || [])
    .filter((p) => p.symbol === symbol)
    .map((p) => ({ side: p.side, pnl: p.realized_pnl == null ? null : Number(p.realized_pnl) }))
  return { atr: t?.atr ?? null, technicals: t, openSameSymbol, recentClosedSameSymbol }
}

// "budget oggi/settimana/mese: usato/max" + set-aside reminder.
export function BudgetStrip({ caps, used, setAside }) {
  if (!caps) return null
  const cell = (win, label) => {
    const cap = caps[win]
    const u = used?.[win] || 0
    const over = cap && u > cap.max
    return (
      <div className="stat">
        <span className="stat-label">{label}</span>
        <span className={`stat-value ${over ? 'neg' : ''}`}>{fmtNum(u, 0)} / {fmtNum(cap.max, 0)}</span>
      </div>
    )
  }
  return (
    <div className="budget-strip">
      <div className="stat-grid">
        {cell('day', 'Budget oggi')}
        {cell('week', 'Settimana')}
        {cell('month', 'Mese')}
        {setAside && (
          <div className="stat">
            <span className="stat-label">Da mettere da parte oggi</span>
            <span className="stat-value pos">{fmtNum(setAside.setAside, 0)}</span>
          </div>
        )}
      </div>
      <p className="muted small">
        Rischio impegnato (REALE) per finestra vs i tuoi tetti. Le posizioni di test sono mostrate a parte e non contano qui.
        {setAside && setAside.realizedProfit > 0 ? ` Profitto realizzato oggi ${fmtNum(setAside.realizedProfit, 0)} — promemoria di risparmio, nessun movimento di denaro.` : ''}
      </p>
    </div>
  )
}

// Warning list — colour = severity only; block ⛔, warn ⚠, note ℹ. Non-directional.
export function GateWarnings({ warnings, okWhenEmpty = true }) {
  if (warnings.length === 0) {
    return okWhenEmpty
      ? <div className="gate-warnings"><p className="gate-ok">Nessun warning: i numeri rientrano nelle tue regole. (Non è un giudizio sulla direzione.)</p></div>
      : null
  }
  return (
    <div className="gate-warnings">
      {warnings.map((w) => (
        <p key={w.code} className={`gate-line gate-${w.severity}`}>
          <span className="gate-tag">{w.severity === 'block' ? '⛔ blocco' : w.severity === 'warn' ? '⚠ warning' : 'ℹ nota'}</span> {w.message}
        </p>
      ))}
    </div>
  )
}

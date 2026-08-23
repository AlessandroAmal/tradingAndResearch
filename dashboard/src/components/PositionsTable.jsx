import { useMemo } from 'react'
import { evaluatePosition, pctOfAccount } from '../lib/risk'
import { fmtNum, fmtPct } from '../lib/format'

// Open positions with live P&L, risk used vs limit, days-to-deadline, and
// breach badges. Portfolio heat + position-count vs limits in the header.
// Read-only: flags only, no orders.
export default function PositionsTable({ positions, priceBySymbol, multiplierBySymbol, settings, nowMs }) {
  const accountSize = Number(settings?.account_size) || 0
  const maxRiskPct = Number(settings?.max_risk_per_trade_pct) || 0
  const maxHeatPct = Number(settings?.max_portfolio_heat_pct) || 0
  const maxPositions = Number(settings?.max_concurrent_positions) || 0
  const warnDays = Number(settings?.deadline_warn_days) || 3

  const evaluated = useMemo(
    () =>
      (positions || []).map((p) => ({
        p,
        e: evaluatePosition(p, {
          current: priceBySymbol[p.symbol] ?? null,
          multiplier: multiplierBySymbol[p.symbol] ?? 1,
          accountSize,
          maxRiskPerTradePct: maxRiskPct,
          warnDays,
          nowMs,
        }),
      })),
    [positions, priceBySymbol, multiplierBySymbol, accountSize, maxRiskPct, warnDays, nowMs],
  )

  const heat = evaluated.reduce((s, { e }) => s + (e.openRisk ?? 0), 0)
  const heatPct = pctOfAccount(heat, accountSize)
  const heatBreached = heatPct != null && maxHeatPct > 0 && heatPct > maxHeatPct
  const posBreached = maxPositions > 0 && evaluated.length > maxPositions

  if (!positions || positions.length === 0) {
    return <p className="muted small">No open positions tracked.</p>
  }

  return (
    <div className="risk-table-wrap">
      <div className="risk-summary">
        <span className={`chip ${heatBreached ? 'bad' : ''}`}>
          Heat {heatPct != null ? fmtPct(heatPct) : '—'} / {maxHeatPct}%
        </span>
        <span className={`chip ${posBreached ? 'bad' : ''}`}>
          Positions {evaluated.length} / {maxPositions || '—'}
        </span>
      </div>

      <table className="risk-table">
        <thead>
          <tr>
            <th>Sym</th><th>Side</th><th>Entry</th><th>Prezzo ora</th><th>P&amp;L</th><th>Risk%</th>
            <th>R</th><th>Days</th><th>Flags</th>
          </tr>
        </thead>
        <tbody>
          {evaluated.map(({ p, e }) => {
            const overRisk = e.riskPerTradeBreached
            const cur = priceBySymbol[p.symbol] ?? null
            const curPct = cur != null && p.entry ? (cur / p.entry - 1) * 100 * (p.side === 'long' ? 1 : -1) : null
            return (
              <tr key={p.id}>
                <td className="sym">{p.symbol}</td>
                <td><span className={`badge ${p.side}`}>{p.side === 'long' ? 'long ▲' : 'short ▼'}</span></td>
                <td>{p.entry == null ? '—' : fmtNum(p.entry, 2)}</td>
                <td className={curPct == null ? 'muted' : curPct >= 0 ? 'pos' : 'neg'}>
                  {cur == null ? '—' : fmtNum(cur, 2)}
                  {curPct != null && <span className="muted small"> ({fmtPct(curPct)})</span>}
                </td>
                <td className={e.pnl == null ? 'muted' : e.pnl >= 0 ? 'pos' : 'neg'}>
                  {e.pnl == null ? '—' : fmtNum(e.pnl, 0)}
                </td>
                <td className={overRisk ? 'neg' : ''}>
                  {e.openRiskPct == null ? '—' : fmtPct(e.openRiskPct)}
                </td>
                <td>{e.rMultiple == null ? '—' : `${e.rMultiple.toFixed(1)}R`}</td>
                <td className={e.deadlineNear ? 'neg' : ''}>
                  {e.daysToDeadline == null ? '—' : `${e.daysToDeadline}d`}
                </td>
                <td className="flags">
                  {e.stopBreached && <span className="flag-badge bad">stop</span>}
                  {overRisk && <span className="flag-badge bad">risk</span>}
                  {e.deadlineNear && <span className="flag-badge warn">deadline</span>}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

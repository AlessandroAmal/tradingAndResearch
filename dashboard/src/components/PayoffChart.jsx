// Minimal SVG payoff chart (price on x, P&L on y) with a zero line and an
// optional breakeven marker. No external chart lib needed for a payoff line.
export default function PayoffChart({ curve, breakeven }) {
  if (!curve || curve.length < 2) return <p className="muted small">No payoff to show.</p>

  const W = 420
  const H = 200
  const PAD = 28
  const xs = curve.map((p) => p.price)
  const ys = curve.map((p) => p.pnl)
  const xMin = Math.min(...xs)
  const xMax = Math.max(...xs)
  const yMin = Math.min(...ys, 0)
  const yMax = Math.max(...ys, 0)
  const sx = (x) => PAD + ((x - xMin) / (xMax - xMin || 1)) * (W - 2 * PAD)
  const sy = (y) => H - PAD - ((y - yMin) / (yMax - yMin || 1)) * (H - 2 * PAD)

  const line = curve.map((p) => `${sx(p.price).toFixed(1)},${sy(p.pnl).toFixed(1)}`).join(' ')
  const zeroY = sy(0)

  return (
    <svg className="payoff" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="payoff at expiry">
      {/* zero P&L line */}
      <line x1={PAD} y1={zeroY} x2={W - PAD} y2={zeroY} stroke="rgba(148,163,184,0.4)" strokeDasharray="4 3" />
      {/* breakeven marker */}
      {breakeven != null && breakeven >= xMin && breakeven <= xMax && (
        <line x1={sx(breakeven)} y1={PAD} x2={sx(breakeven)} y2={H - PAD}
          stroke="rgba(59,130,246,0.6)" strokeDasharray="3 3" />
      )}
      <polyline points={line} fill="none" stroke="#3b82f6" strokeWidth="2" />
      {/* axis labels */}
      <text x={PAD} y={H - 6} className="payoff-lbl">{xMin.toFixed(0)}</text>
      <text x={W - PAD} y={H - 6} textAnchor="end" className="payoff-lbl">{xMax.toFixed(0)}</text>
      <text x={4} y={sy(yMax) + 4} className="payoff-lbl">{yMax.toFixed(0)}</text>
      <text x={4} y={sy(yMin) + 4} className="payoff-lbl">{yMin.toFixed(0)}</text>
    </svg>
  )
}

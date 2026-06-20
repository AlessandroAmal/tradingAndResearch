import { countdown } from '../lib/format'

// Read-only list of open tracked positions.
export default function PositionsList({ positions, nowMs }) {
  if (!positions || positions.length === 0) {
    return <p className="muted small">No open positions tracked.</p>
  }
  return (
    <ul className="pos-list">
      {positions.map((p) => (
        <li key={p.id} className="pos-row">
          <span className={`badge ${p.side}`}>{p.side}</span>
          <span className="sym">{p.symbol}</span>
          <span className="muted small">
            {p.size} @ {p.entry}
            {p.stop ? ` · stop ${p.stop}` : ''}
            {p.target ? ` · tgt ${p.target}` : ''}
          </span>
          {p.deadline && (
            <span className="countdown small">
              {countdown(`${p.deadline}T23:59:59Z`, nowMs)}
            </span>
          )}
        </li>
      ))}
    </ul>
  )
}

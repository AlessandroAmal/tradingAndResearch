// Shared visual indicators — a coherent gauge/bar language for the EXISTING
// scalar metrics. Honesty floor (CLAUDE.md): every gauge ALWAYS shows the
// number, carries its own honest label, and is STATE not ACTION; colour is used
// only for meaning (severity / pos-neg) — never decorative. No gauge ever says
// buy/sell.
import { fmtNum, fmtPct } from '../lib/format'

// Implied probability — THE calibrated number; shown prominently, neutral fill
// (it's market odds/magnitude, not a directional colour).
export function ProbBar({ value, caption }) {
  const pct = value == null ? null : Math.max(0, Math.min(1, value)) * 100
  return (
    <div className="ind">
      <div className="ind-row">
        <span className="ind-cap">{caption}</span>
        <span className="ind-num">{pct == null ? '—' : fmtPct(pct).replace('+', '')}</span>
      </div>
      <div className="ind-track">
        {pct != null && <span className="ind-fill neutral" style={{ width: `${pct}%` }} />}
        <span className="ind-mid" />
      </div>
    </div>
  )
}

// Value vs a configured limit — severity ramp (ok → caution → breach).
export function SeverityBar({ value, limit, caption, unit = '%', digits = 2 }) {
  const v = value == null ? null : value
  const ratio = v != null && limit ? v / limit : null
  const sev = ratio == null ? 'neutral' : ratio >= 1 ? 'neg' : ratio >= 0.75 ? 'warn' : 'pos'
  const w = ratio == null ? 0 : Math.max(0, Math.min(1, ratio)) * 100
  return (
    <div className="ind">
      <div className="ind-row">
        <span className="ind-cap">{caption}</span>
        <span className={`ind-num ${sev}`}>
          {v == null ? '—' : `${fmtNum(v, digits)}${unit}`}
          {limit ? <span className="ind-lim"> / {fmtNum(limit, digits)}{unit}</span> : null}
        </span>
      </div>
      <div className="ind-track">
        {ratio != null && <span className={`ind-fill ${sev}`} style={{ width: `${w}%` }} />}
        {limit ? <span className="ind-limmark" style={{ left: '100%' }} /> : null}
      </div>
    </div>
  )
}

// Percentile (0..1) over a lookback — neutral fill; the extremes (crowded) are
// shaded as caution. Used for skew/COT positioning.
export function PercentileBar({ pct, caption, hi = 0.9, lo = 0.1 }) {
  const v = pct == null ? null : Math.max(0, Math.min(1, pct))
  const extreme = v != null && (v >= hi || v <= lo)
  return (
    <div className="ind">
      <div className="ind-row">
        <span className="ind-cap">{caption}</span>
        <span className={`ind-num ${extreme ? 'warn' : ''}`}>{v == null ? '—' : `${Math.round(v * 100)}°`}</span>
      </div>
      <div className="ind-track pctile">
        <span className="ind-zone lo" style={{ width: `${lo * 100}%` }} />
        <span className="ind-zone hi" style={{ width: `${(1 - hi) * 100}%` }} />
        {v != null && <span className="ind-marker" style={{ left: `${v * 100}%` }} />}
      </div>
    </div>
  )
}

// RSI (0..100) with the instrument-tuned threshold ticks. Zone colour = caution
// at the extremes; the number is always there.
export function RsiBar({ value, overbought = 70, oversold = 30 }) {
  const v = value == null ? null : Math.max(0, Math.min(100, value))
  const zone = v == null ? 'neutral' : v >= overbought ? 'warn' : v <= oversold ? 'warn' : 'neutral'
  return (
    <div className="ind">
      <div className="ind-row">
        <span className="ind-cap">RSI <span className="muted">({oversold}/{overbought})</span></span>
        <span className={`ind-num ${zone}`}>{v == null ? '—' : Math.round(v)}</span>
      </div>
      <div className="ind-track">
        {v != null && <span className="ind-fill neutral" style={{ width: `${v}%` }} />}
        <span className="ind-tick" style={{ left: `${oversold}%` }} />
        <span className="ind-tick" style={{ left: `${overbought}%` }} />
      </div>
    </div>
  )
}

// Compact diverging confluence bar for instrument tiles (−100..+100). Marker in
// --text-primary; colour ramp = conditions, NOT an action.
export function MiniConfluence({ score }) {
  const has = score != null && !Number.isNaN(score)
  const pos = has ? (Math.max(-100, Math.min(100, score)) + 100) / 2 : 50
  const dir = !has ? 'muted' : score > 0 ? 'pos' : score < 0 ? 'neg' : 'muted'
  return (
    <div className="miniconf" title="lettura di confluenza (condizioni, non previsione)">
      <span className="miniconf-track">
        <span className="miniconf-mid" />
        {has && <span className="miniconf-marker" style={{ left: `${pos}%` }} />}
      </span>
      <span className={`miniconf-val ${dir}`}>{has ? `${score > 0 ? '+' : ''}${Math.round(score)}` : '—'}</span>
    </div>
  )
}

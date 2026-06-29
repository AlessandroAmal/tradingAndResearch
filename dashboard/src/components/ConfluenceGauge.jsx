// SIGNATURE — the confluence "lancetta". An arc gauge for the −100..+100
// reading: dark arc with a DIVERGENT scale (red ← neutral grey → green = the
// CONDITIONS), a needle in --text-primary, the big mono value at the centre.
// It is NOT a buy/sell dial: the caveat is rendered right under it by the caller.
import { useMemo } from 'react'

const NEG = [0xe5, 0x48, 0x4d]
const MID = [0x5b, 0x65, 0x73]
const POS = [0x3f, 0xa6, 0x6b]

function lerp(a, b, t) { return a.map((x, i) => Math.round(x + (b[i] - x) * t)) }
function hex([r, g, b]) { return `rgb(${r},${g},${b})` }
function rampColor(t) { // t in [0,1] across the arc (0=−100 red, 1=+100 green)
  return t <= 0.5 ? hex(lerp(NEG, MID, t / 0.5)) : hex(lerp(MID, POS, (t - 0.5) / 0.5))
}

// score -> angle in degrees (180° left .. 0° right). 0 -> 90° (up).
const angleOf = (s) => 90 - (Math.max(-100, Math.min(100, s)) * 0.9)
function polar(cx, cy, r, deg) {
  const a = (deg * Math.PI) / 180
  return [cx + r * Math.cos(a), cy - r * Math.sin(a)]
}
function arc(cx, cy, r, a0, a1) {
  const [x0, y0] = polar(cx, cy, r, a0)
  const [x1, y1] = polar(cx, cy, r, a1)
  return `M ${x0.toFixed(2)} ${y0.toFixed(2)} A ${r} ${r} 0 0 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`
}

export default function ConfluenceGauge({ score, label, direction }) {
  const W = 240, H = 138, cx = 120, cy = 118, r = 92, sw = 13
  const segs = useMemo(() => {
    const n = 28, out = []
    for (let i = 0; i < n; i++) {
      const t0 = i / n, t1 = (i + 1) / n
      // map t (0..1) to angle: t=0 -> 180°, t=1 -> 0°
      const a0 = 180 - t0 * 180, a1 = 180 - t1 * 180
      out.push({ d: arc(cx, cy, r, a0, a1), c: rampColor((t0 + t1) / 2) })
    }
    return out
  }, [])

  const hasScore = score != null && !Number.isNaN(score)
  const needleA = angleOf(hasScore ? score : 0)
  const [nx, ny] = polar(cx, cy, r - 4, needleA)
  const dirClass = { bullish: 'pos', bearish: 'neg' }[direction] || 'muted'

  return (
    <div className="gauge">
      <svg viewBox={`0 0 ${W} ${H}`} className="gauge-svg" role="img"
        aria-label={`lettura di confluenza ${hasScore ? score : 'n/d'} — ${label || ''}`}>
        {segs.map((s, i) => (
          <path key={i} d={s.d} stroke={s.c} strokeWidth={sw} fill="none"
            strokeLinecap="butt" opacity="0.85" />
        ))}
        {/* neutral centre tick */}
        <line x1={cx} y1={cy - r - sw / 2} x2={cx} y2={cy - r + sw / 2}
          stroke="var(--bg-base)" strokeWidth="2" />
        {hasScore && (
          <>
            <line x1={cx} y1={cy} x2={nx.toFixed(2)} y2={ny.toFixed(2)}
              stroke="var(--text-primary)" strokeWidth="2.5" strokeLinecap="round" />
            <circle cx={cx} cy={cy} r="5" fill="var(--text-primary)" />
          </>
        )}
        <text x={cx} y={cy - 22} textAnchor="middle" className={`gauge-value ${dirClass}`}>
          {hasScore ? `${score > 0 ? '+' : ''}${Math.round(score)}` : '—'}
        </text>
        <text x={cx - r + 2} y={cy + 14} textAnchor="middle" className="gauge-end">−100</text>
        <text x={cx + r - 2} y={cy + 14} textAnchor="middle" className="gauge-end">+100</text>
      </svg>
      <div className={`gauge-label ${dirClass}`}>{label || 'dati insufficienti'}</div>
    </div>
  )
}

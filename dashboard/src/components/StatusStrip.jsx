import { useEffect, useMemo, useState } from 'react'
import { evaluatePosition, pctOfAccount } from '../lib/risk'
import { fmtNum, fmtPct, countdown } from '../lib/format'
import { fetchLatestAnyBriefing } from '../api/data'
import InfoTip from './InfoTip'
import { RISK_HELP_BY_KEY as RH } from '../data/guide'

// Short glossary for the strip's own metrics (kept local, no jargon left bare).
const SS_TIP = {
  pnl: { label: 'P&L aperto', text: 'Profitto/perdita NON realizzato delle posizioni reali aperte, ai prezzi correnti e col point value corretto. Cambia col prezzo; si realizza solo alla chiusura.' },
  next: { label: 'Prossimo catalizzatore', text: 'Il prossimo evento ad alto impatto in calendario, col conto alla rovescia. Vicino a un evento le letture di condizioni possono ribaltarsi.' },
  briefing: { label: 'Ultimo briefing', text: 'Il più recente briefing AI generato (tipo + titolo). Sintetizza le news, non prevede il mercato.' },
}

// At-a-glance signature strip: open P&L, portfolio heat vs limit (risk-toned),
// active breach count, next high-impact catalyst, latest briefing title.
// Reuses data already loaded by App — no new data wiring. Colour = meaning only.
export default function StatusStrip({ positions, priceBySymbol, multiplierBySymbol, settings, events, nowMs }) {
  const [briefing, setBriefing] = useState(null)

  useEffect(() => {
    let cancelled = false
    fetchLatestAnyBriefing().then(({ data }) => {
      if (!cancelled) setBriefing(data || null)
    })
    return () => { cancelled = true }
  }, [])

  const m = useMemo(() => {
    const accountSize = Number(settings?.account_size) || 0
    const maxRiskPct = Number(settings?.max_risk_per_trade_pct) || 0
    const maxHeatPct = Number(settings?.max_portfolio_heat_pct) || 0
    const maxPositions = Number(settings?.max_concurrent_positions) || 0
    const warnDays = Number(settings?.deadline_warn_days) || 3

    let pnl = 0
    let pnlKnown = false
    let heat = 0
    let breaches = 0
    for (const p of positions || []) {
      const e = evaluatePosition(p, {
        current: priceBySymbol[p.symbol] ?? null,
        multiplier: multiplierBySymbol[p.symbol] ?? 1,
        accountSize, maxRiskPerTradePct: maxRiskPct, warnDays, nowMs,
      })
      if (e.pnl != null) { pnl += e.pnl; pnlKnown = true }
      heat += e.openRisk ?? 0
      if (e.stopBreached || e.riskPerTradeBreached || e.deadlineNear) breaches++
    }
    const heatPct = pctOfAccount(heat, accountSize)
    const heatBreached = heatPct != null && maxHeatPct > 0 && heatPct > maxHeatPct
    if (heatBreached) breaches++
    if (maxPositions > 0 && (positions?.length || 0) > maxPositions) breaches++

    // next high-impact catalyst (fallback to any upcoming)
    const upcoming = (events || []).filter((e) => new Date(e.event_time).getTime() > nowMs)
    const next = upcoming.find((e) => e.importance === 'high') || upcoming[0] || null

    return { pnl, pnlKnown, heatPct, maxHeatPct, heatBreached, breaches, next }
  }, [positions, priceBySymbol, multiplierBySymbol, settings, events, nowMs])

  const heatRatio = m.heatPct != null && m.maxHeatPct ? m.heatPct / m.maxHeatPct : 0
  const heatTone = m.heatBreached ? 'tone-neg' : heatRatio > 0.8 ? 'tone-warn' : ''
  const pnlTone = !m.pnlKnown ? '' : m.pnl >= 0 ? 'tone-pos' : 'tone-neg'

  return (
    <section className="statusstrip" aria-label="Sintesi a colpo d'occhio">
      <div className={`ss-item ${pnlTone}`}>
        <span className="ss-label">P&amp;L aperto <InfoTip text={SS_TIP.pnl.text} label={SS_TIP.pnl.label} /></span>
        <span className={`ss-value ${!m.pnlKnown ? 'muted' : m.pnl >= 0 ? 'pos' : 'neg'}`}>
          {m.pnlKnown ? fmtNum(m.pnl, 0) : '—'}
        </span>
      </div>

      <div className={`ss-item ${heatTone}`}>
        <span className="ss-label">Heat portafoglio <InfoTip text={RH.portfolio_heat.text} label={RH.portfolio_heat.label} /></span>
        <span className={`ss-value ${m.heatBreached ? 'neg' : heatRatio > 0.8 ? 'warn' : ''}`}>
          {m.heatPct != null ? fmtPct(m.heatPct) : '—'}
          <span className="ss-sub"> / {m.maxHeatPct || '—'}%</span>
        </span>
      </div>

      <div className={`ss-item ${m.breaches > 0 ? 'tone-neg' : ''}`}>
        <span className="ss-label">Violazioni attive <InfoTip text={RH.breach.text} label={RH.breach.label} /></span>
        <span className={`ss-value ${m.breaches > 0 ? 'neg' : ''}`}>{m.breaches}</span>
      </div>

      <div className="ss-item">
        <span className="ss-label">Prossimo catalizzatore <InfoTip text={SS_TIP.next.text} label={SS_TIP.next.label} /></span>
        <span className="ss-value sans">
          {m.next ? (
            <>
              {countdown(m.next.event_time, nowMs)}
              <span className="ss-sub"> · {m.next.title?.slice(0, 28) || ''}</span>
            </>
          ) : '—'}
        </span>
      </div>

      <div className="ss-item">
        <span className="ss-label">Ultimo briefing <InfoTip text={SS_TIP.briefing.text} label={SS_TIP.briefing.label} /></span>
        <span className="ss-value sans" title={briefing?.title || ''}>
          {briefing ? `${briefing.kind} · ${briefing.title || ''}` : '—'}
        </span>
      </div>
    </section>
  )
}

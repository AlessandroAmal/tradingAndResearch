import { useEffect, useMemo, useState } from 'react'
import { fetchPositions } from '../api/data'
import { tradesFromPositions, expectancyStats, ruinCurve, kellyAdjusted, avgRiskFrac, MIN_SAMPLE } from '../lib/expectancy'
import { fmtNum, fmtPct } from '../lib/format'
import InfoTip from '../components/InfoTip'
import { RISK_HELP_BY_KEY as RH } from '../data/guide'

// EXPECTANCY & SOPRAVVIVENZA — the long-run math of the user's OWN trading, on
// their OWN data. MEASURED, never predicted; n + intervals always visible.
export default function Expectancy({ settings, multiplierBySymbol, refreshKey = 0 }) {
  const [closed, setClosed] = useState([])
  const [scope, setScope] = useState('all')      // all | real | paper
  const [symbol, setSymbol] = useState('')
  const [tag, setTag] = useState('')

  useEffect(() => { fetchPositions('closed').then(({ data }) => setClosed(data || [])) }, [refreshKey])

  const accountSize = Number(settings?.account_size) || 0
  const maxRisk = Number(settings?.max_risk_per_trade_pct ?? 1)

  const allTrades = useMemo(() => tradesFromPositions(closed, multiplierBySymbol), [closed, multiplierBySymbol])
  const symbols = useMemo(() => [...new Set(allTrades.map((t) => t.symbol))].sort(), [allTrades])
  const tags = useMemo(() => [...new Set(allTrades.map((t) => t.tag).filter(Boolean))].sort(), [allTrades])

  const trades = useMemo(() => allTrades.filter((t) =>
    (scope === 'all' || (scope === 'real' ? !t.paper : t.paper))
    && (!symbol || t.symbol === symbol) && (!tag || t.tag === tag)), [allTrades, scope, symbol, tag])

  const stats = useMemo(() => expectancyStats(trades), [trades])
  const currentFrac = useMemo(() => avgRiskFrac(trades, accountSize, maxRisk), [trades, accountSize, maxRisk])
  const rr = stats.avgWinR && stats.avgLossR ? stats.avgWinR / stats.avgLossR : null
  const curve = useMemo(() => (stats.winRate && rr && currentFrac
    ? ruinCurve({ winRate: stats.winRate, rr, currentFrac }) : []), [stats, rr, currentFrac])
  const kelly = useMemo(() => kellyAdjusted(stats), [stats])

  const dim = stats.sufficient ? '' : 'muted'

  return (
    <div className="desk">
      <section className="panel">
        <header className="panel-head">
          <h2>Expectancy & sopravvivenza</h2>
          <span className="muted small">misurata sui TUOI trade chiusi · niente previsioni</span>
        </header>
        <div className="desk-controls">
          <label>Ambito
            <select value={scope} onChange={(e) => setScope(e.target.value)}>
              <option value="all">tutti</option><option value="real">solo reali</option><option value="paper">solo paper</option>
            </select></label>
          <label>Strumento
            <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
              <option value="">tutti</option>{symbols.map((s) => <option key={s} value={s}>{s}</option>)}
            </select></label>
          {tags.length > 0 && (
            <label>Setup-tag
              <select value={tag} onChange={(e) => setTag(e.target.value)}>
                <option value="">tutti</option>{tags.map((t) => <option key={t} value={t}>{t}</option>)}
              </select></label>
          )}
          <span className="muted small">paper e reali separabili: le paper insegnano ma non provano l’esecuzione reale.</span>
        </div>

        {stats.n === 0 ? <p className="muted small">Nessun trade chiuso in questo filtro. Chiudi qualche posizione (reale o paper) per iniziare a misurare.</p> : (
          <>
            {!stats.sufficient && (
              <p className="honest-note">Campione insufficiente (n={stats.n} &lt; {MIN_SAMPLE}): questi numeri sono <strong>rumore</strong> — continua a raccogliere. Mostrati attenuati.</p>
            )}
            <div className="stat-grid">
              <Stat label="Trade (n)" value={stats.n} />
              <Stat label="Win rate" value={pct(stats.winRate)} sub={ci(stats.winRateCi)} cls={dim} />
              <Stat label="R medio vincenti" value={r(stats.avgWinR)} cls={dim} />
              <Stat label="R medio perdenti" value={stats.avgLossR == null ? '—' : `−${fmtNum(stats.avgLossR, 2)}R`} cls={dim} />
              <Stat label="Expectancy / trade" value={r(stats.expectancyR)} sub={ci(stats.expectancyRCi, 'R')} cls={dim} />
              <Stat label="Expectancy €" value={stats.expectancyEur == null ? '—' : fmtNum(stats.expectancyEur, 0)} sub={ci(stats.expectancyEurCi, '€', 0)} cls={dim} />
              <Stat label="Profit factor" value={stats.profitFactor == null ? '—' : fmtNum(stats.profitFactor, 2)} cls={dim} />
              <Stat label="Max perdite di fila" value={stats.maxConsecutiveLosses} cls={dim} />
            </div>
          </>
        )}
      </section>

      {/* RISK OF RUIN */}
      {curve.length > 0 && (
        <section className="panel">
          <header className="panel-head"><h2>Rischio di rovina</h2><span className="muted small">la size decide se sopravvivi abbastanza a lungo</span></header>
          <p className="muted small">P(perdere il 50% del capitale prima di raddoppiarlo), Monte Carlo 10k sulle TUE statistiche misurate (win {pct(stats.winRate)}, R/R {fmtNum(rr, 2)}).</p>
          <div className="ruin-bars">
            {curve.map((c) => (
              <div key={c.riskFrac} className={`ruin-bar ${c.current ? 'current' : ''}`}>
                <span className="ruin-lab">{fmtNum(c.riskFrac * 100, 1)}%{c.current ? ' ◄ tu' : ''}</span>
                <div className="ruin-track"><div className="ruin-fill" style={{ width: `${(c.ruin ?? 0) * 100}%` }} /></div>
                <span className="ruin-val">{c.ruin == null ? '—' : fmtPct(c.ruin * 100).replace('+', '')}</span>
              </div>
            ))}
          </div>
          <p className="muted small caveat">Rischio % per trade sull’asse; la tua posizione attuale (~{fmtNum(currentFrac * 100, 1)}%) è evidenziata. Misura, non una previsione.</p>
        </section>
      )}

      {/* KELLY */}
      <section className="panel">
        <header className="panel-head"><h2>Size Kelly (aggiustata per incertezza) <InfoTip text={RH.position_sizing.text} label={RH.position_sizing.label} /></h2></header>
        {!kelly.proven ? (
          <p className="honest-note">{kelly.note} <span className="muted small">In raccolta dati: n={stats.n}/{MIN_SAMPLE}.</span></p>
        ) : (
          <>
            <div className="stat-grid">
              <Stat label="Kelly (bound inferiore)" value={pct(kelly.kellyLower)} />
              <Stat label="½-Kelly" value={pct(kelly.halfKelly)} />
              <Stat label="¼-Kelly (consigliata)" value={pct(kelly.quarterKelly)} cls="pos" />
              <Stat label="La tua size media" value={pct(currentFrac)} />
            </div>
            {currentFrac > kelly.halfKelly && (
              <p className="gate-line gate-warn"><span className="gate-tag">⚠ size</span> Stai usando più di ½-Kelly ({pct(currentFrac)} vs {pct(kelly.halfKelly)}): oltre il dimostrato → più rischio di rovina.</p>
            )}
            <p className="muted small caveat">{kelly.note} Usa il bound INFERIORE del win rate (ciò che è dimostrato, non la media).</p>
          </>
        )}
      </section>

      {/* PROCESS SCORECARD */}
      <ProcessScorecard trades={trades} />
    </div>
  )
}

function ProcessScorecard({ trades }) {
  const clean = trades.filter((t) => !t.forced)
  const forced = trades.filter((t) => t.forced)
  const sc = { clean: expectancyStats(clean), forced: expectancyStats(forced) }
  return (
    <section className="panel">
      <header className="panel-head"><h2>Scorecard di processo</h2><span className="muted small">la disciplina è misurabile</span></header>
      <div className="lens-grid">
        <div className="lens-card">
          <span className="lens-tag">Dentro le regole (n={sc.clean.n})</span>
          <p>Win {pct(sc.clean.winRate)} · Expectancy {r(sc.clean.expectancyR)} · PF {sc.clean.profitFactor == null ? '—' : fmtNum(sc.clean.profitFactor, 2)}</p>
        </div>
        <div className="lens-card">
          <span className="lens-tag">Forzati oltre i warning (n={sc.forced.n})</span>
          <p>Win {pct(sc.forced.winRate)} · Expectancy {r(sc.forced.expectancyR)} · PF {sc.forced.profitFactor == null ? '—' : fmtNum(sc.forced.profitFactor, 2)}</p>
        </div>
      </div>
      <p className="muted small caveat">% forzati: {trades.length ? fmtPct((forced.length / trades.length) * 100).replace('+', '') : '—'}. Con n piccolo entrambe le colonne sono rumore. Misura del TUO processo, non un giudizio.</p>
    </section>
  )
}

const pct = (v) => (v == null ? '—' : fmtPct(v * 100).replace('+', ''))
const r = (v) => (v == null ? '—' : `${v > 0 ? '+' : ''}${fmtNum(v, 2)}R`)
function ci(pair, unit = '', d = 0) {
  if (!pair) return null
  const f = unit === 'R' ? (x) => `${fmtNum(x, 2)}R` : unit === '€' ? (x) => `${fmtNum(x, d)}€` : (x) => fmtPct(x * 100).replace('+', '')
  return `IC95% ${f(pair[0])}…${f(pair[1])}`
}
function Stat({ label, value, sub, cls = '' }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className={`stat-value ${cls}`}>{value}</span>
      {sub && <span className="muted small">{sub}</span>}
    </div>
  )
}

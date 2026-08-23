import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchDecisionBoards, fetchDecisionBoard, insertPosition, insertJournalEntry } from '../api/data'
import { positionSize } from '../lib/risk'
import { betMath, verdict, scenarioLadder, optionIllustration, impliedOnLevels } from '../lib/bench'
import { evaluateGate } from '../lib/gate'
import { committedInWindows, setAsideToday } from '../lib/discipline'
import { capsFromSettings, gateInputsForSymbol, BudgetStrip, GateWarnings, killswitchInputs } from '../components/GateShared'
import { tradesFromPositions, expectancyStats, kellyAdjusted, MIN_SAMPLE } from '../lib/expectancy'
import { fmtNum, fmtPct, countdown } from '../lib/format'
import InfoTip from '../components/InfoTip'
import { DECISION_HELP_BY_KEY as DH } from '../data/guide'

const todayISO = () => new Date().toISOString().slice(0, 10)

// BANCO DI DECISIONE — organises the numbers around ONE bet. READ-ONLY, never an
// order, never a fabricated probability: the only odds are option-implied.
export default function DecisionBench({ instruments, settings, positions, closedPositions, priceBySymbol, multiplierBySymbol, events, initialSymbol = null, onSaved }) {
  const [symbols, setSymbols] = useState([])
  const [board, setBoard] = useState(null)
  const [f, setF] = useState({ symbol: '', direction: 'long', horizon: 10, entry: '', stop: '', target: '', riskPct: '' })
  const [status, setStatus] = useState(null)
  const [saving, setSaving] = useState(false)
  const [nowMs, setNowMs] = useState(Date.now())
  const set = (k, v) => setF((s) => ({ ...s, [k]: v }))

  useEffect(() => { const t = setInterval(() => setNowMs(Date.now()), 30_000); return () => clearInterval(t) }, [])
  useEffect(() => {
    fetchDecisionBoards().then(({ data }) => {
      const rows = data || []
      setSymbols(rows)
      const wanted = initialSymbol && rows.some((r) => r.symbol === initialSymbol) ? initialSymbol : null
      setF((s) => ({ ...s, symbol: s.symbol || wanted || (rows[0]?.symbol || '') }))
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  useEffect(() => {
    if (!f.symbol) return
    fetchDecisionBoard(f.symbol).then(({ data }) => {
      const b = data?.board || null
      setBoard(b)
      // LOW-FRICTION prefill: entry = current price; stop = k×ATR (long: below,
      // short: above); target = R/R default × the stop distance; rischio% = config.
      // The user only has to change 1-2 fields to get a useful read.
      setF((s) => {
        const price = b?.last
        const atr = b?.technicals?.atr
        const k = Number(settings?.stop_atr_min_multiple ?? 1.5)
        const rr = Number(settings?.rr_min ?? 1.5)
        const dir = s.direction
        const next = { ...s }
        if (!s.entry && price != null) next.entry = String(price)
        if (!s.stop && price != null && atr) {
          const dist = k * atr
          next.stop = String(Number((dir === 'long' ? price - dist : price + dist).toFixed(4)))
        }
        if (!s.target && price != null && atr) {
          const dist = k * atr * rr
          next.target = String(Number((dir === 'long' ? price + dist : price - dist).toFixed(4)))
        }
        if (!s.riskPct && settings?.max_risk_per_trade_pct != null) next.riskPct = String(settings.max_risk_per_trade_pct)
        return next
      })
    })
  }, [f.symbol, settings])

  const multiplier = Number(multiplierBySymbol?.[f.symbol]) || 1
  const accountSize = Number(settings?.account_size) || 0
  const maxRisk = Number(settings?.max_risk_per_trade_pct ?? 1)
  const costs = board?.costs || { spread_bps: 5, commission: 0 }
  const entry = Number(f.entry)
  const stop = f.stop === '' ? null : Number(f.stop)
  const target = f.target === '' ? null : Number(f.target)
  const horizon = Math.max(Number(f.horizon) || 1, 1)
  const atr = board?.technicals?.atr ?? null

  const size = useMemo(() => {
    const s = positionSize(accountSize, Number(f.riskPct) || maxRisk, entry, stop, multiplier)
    return s != null ? s : 0
  }, [accountSize, f.riskPct, maxRisk, entry, stop, multiplier])

  // Kelly (from the user's OWN closed trades) alongside the fixed-risk size —
  // only when there's a demonstrated edge; else "collecting data: n=X/20".
  const kelly = useMemo(() => kellyAdjusted(expectancyStats(tradesFromPositions(closedPositions, multiplierBySymbol))), [closedPositions, multiplierBySymbol])
  const kellySize = useMemo(() => {
    if (!kelly.proven || !(accountSize > 0) || stop == null || !(Math.abs(entry - stop) > 0)) return null
    return (kelly.quarterKelly * accountSize) / (Math.abs(entry - stop) * multiplier)
  }, [kelly, accountSize, entry, stop, multiplier])

  const math = useMemo(() => betMath({ entry, stop, target, size, multiplier, spreadBps: costs.spread_bps, commission: costs.commission }), [entry, stop, target, size, multiplier, costs])
  const implied = useMemo(() => impliedOnLevels({ implied: board?.implied, target, stop, horizonDays: horizon, direction: f.direction }), [board, target, stop, horizon, f.direction])
  const theVerdict = useMemo(() => verdict(math.breakevenWinrate, implied.probTarget), [math, implied])
  const ladder = useMemo(() => scenarioLadder({ entry, stop, target, atr, direction: f.direction, size, multiplier }), [entry, stop, target, atr, f.direction, size, multiplier])
  const option = useMemo(() => {
    const spot = board?.implied?.spot ?? board?.last
    const iv = implied.atmIv
    if (!spot || !iv) return null
    return optionIllustration({ spot, strike: entry || spot, direction: f.direction, T: horizon / 365, r: board?.implied?.risk_free_rate ?? 0.04, sigma: iv, target, contractSize: multiplier })
  }, [board, implied, entry, f.direction, horizon, target, multiplier])

  // events within the horizon window
  const eventsInWindow = useMemo(() => {
    const end = nowMs + horizon * 86_400_000
    return (board?.events || []).filter((e) => {
      const t = new Date(e.event_time).getTime()
      return t >= nowMs && t <= end
    })
  }, [board, horizon, nowMs])

  // integrated gate
  const caps = useMemo(() => capsFromSettings(settings), [settings])
  const budgetUsed = useMemo(() => committedInWindows(positions, multiplierBySymbol), [positions, multiplierBySymbol])
  const disc = useMemo(() => gateInputsForSymbol({ symbol: f.symbol, technicals: board?.technicals, positions, closedPositions, current: priceBySymbol?.[f.symbol], multiplier }), [f.symbol, board, positions, closedPositions, priceBySymbol, multiplier])
  const gate = useMemo(() => evaluateGate({
    symbol: f.symbol, side: f.direction, entry, stop, target, size, multiplier,
    accountSize, maxRiskPerTradePct: maxRisk, maxPortfolioHeatPct: Number(settings?.max_portfolio_heat_pct ?? 6),
    maxConcurrentPositions: Number(settings?.max_concurrent_positions ?? 8), rrMin: Number(settings?.rr_min ?? 1.5),
    openCount: (positions || []).length, thesis: 'bench', leanDirection: board?.synthesis?.lean?.direction,
    events: events || board?.events || [], eventWarnHours: Number(settings?.event_warn_hours ?? 48),
    requireThesis: false, atr: disc.atr, stopAtrMinMultiple: Number(settings?.stop_atr_min_multiple ?? 1.5),
    technicals: disc.technicals, recentClosedSameSymbol: disc.recentClosedSameSymbol, openSameSymbol: disc.openSameSymbol,
    budgetCaps: caps, budgetUsed,
    ...killswitchInputs({ settings, closedPositions, symbol: f.symbol, side: f.direction, paper: true }),
  }), [f, entry, stop, target, size, multiplier, accountSize, maxRisk, settings, positions, closedPositions, board, events, disc, caps, budgetUsed])

  const monitorTest = useCallback(async () => {
    if (!(entry > 0)) return setStatus({ type: 'error', msg: 'Entry deve essere > 0.' })
    if (stop == null) return setStatus({ type: 'error', msg: 'Stop obbligatorio: senza stop non si registra.' })
    if (!(size > 0)) return setStatus({ type: 'error', msg: 'Size non calcolabile (controlla rischio%/stop).' })
    setSaving(true); setStatus(null)
    const inst = instruments?.find((i) => i.symbol === f.symbol)
    const snapshot = {
      captured_at: new Date().toISOString(), source: 'decision_bench',
      direction: f.direction, horizon_days: horizon,
      breakeven_winrate: math.breakevenWinrate, breakeven_winrate_no_cost: math.breakevenWinrateNoCost,
      implied_prob_target: implied.probTarget, implied_prob_stop: implied.probStop,
      implied_expiry_days: implied.expiryDays, rr: math.rr, cost_amount: math.costAmount,
      lean_direction: board?.synthesis?.lean?.direction ?? null,
    }
    const { data: pos, error } = await insertPosition({
      instrument_id: inst?.id ?? null, symbol: f.symbol, side: f.direction, size,
      entry, stop, target, broker: 'TEST', status: 'open', paper: true,
      thesis: `Banco decisione: ${f.direction} ${horizon}g, pareggio ${math.breakevenWinrate != null ? (math.breakevenWinrate * 100).toFixed(0) + '%' : '—'} vs mercato ${implied.probTarget != null ? (implied.probTarget * 100).toFixed(0) + '%' : '—'}.`,
      entry_conditions: snapshot,
    })
    if (error) { setSaving(false); return setStatus({ type: 'error', msg: error.message }) }
    await insertJournalEntry({
      position_id: pos?.id ?? null, symbol: f.symbol, thesis: 'Test da Banco di decisione.',
      entry_price: entry, stop, size, entry_date: todayISO(), reviewed: false,
      notes: `TEST · ${f.direction} · orizzonte ${horizon}g · pareggio ${math.breakevenWinrate != null ? (math.breakevenWinrate * 100).toFixed(0) + '%' : '—'} vs odds impliciti ${implied.probTarget != null ? (implied.probTarget * 100).toFixed(0) + '%' : '—'} (snapshot salvato).`,
    })
    setSaving(false)
    setStatus({ type: 'ok', msg: 'Posizione TEST aperta (nessun ordine) + snapshot salvato.' })
    onSaved?.()
  }, [entry, stop, size, f, horizon, math, implied, board, instruments, onSaved])

  return (
    <div className="desk">
      <section className="panel">
        <header className="panel-head">
          <h2>Banco di decisione</h2>
          <span className="muted small">i numeri attorno a UNA scommessa · read-only · la decisione è tua</span>
        </header>
        {symbols.length === 0 && <p className="muted small">Nessun decision board. Premi <strong>Aggiorna</strong>.</p>}
        <div className="bench-form">
          <label>Strumento
            <select value={f.symbol} onChange={(e) => set('symbol', e.target.value)}>
              {symbols.map((s) => <option key={s.symbol} value={s.symbol}>{s.name || s.symbol}</option>)}
            </select></label>
          <label>Direzione
            <select value={f.direction} onChange={(e) => set('direction', e.target.value)}>
              <option value="long">long</option><option value="short">short</option>
            </select></label>
          <label>Orizzonte (giorni)<input type="number" min="1" value={f.horizon} onChange={(e) => set('horizon', e.target.value)} /></label>
          <label>Entry<input type="number" step="any" value={f.entry} onChange={(e) => set('entry', e.target.value)} placeholder={board?.last != null ? String(board.last) : ''} /></label>
          <label>Stop<input type="number" step="any" value={f.stop} onChange={(e) => set('stop', e.target.value)} /></label>
          <label>Target<input type="number" step="any" value={f.target} onChange={(e) => set('target', e.target.value)} /></label>
          <label>Rischio %<input type="number" step="any" placeholder={String(maxRisk)} value={f.riskPct} onChange={(e) => set('riskPct', e.target.value)} /></label>
        </div>
        <div className="stat-grid">
          <Stat label="Prezzo ora" value={board?.last == null ? '—' : fmtNum(board.last, 2)} />
          <Stat label="Size (dal rischio%)" value={size ? fmtNum(size, 2) : '—'} />
          <Stat label="Point value" value={`×${multiplier}`} cls={multiplier === 1 ? 'warn' : ''} />
          <Stat label="Costo stimato (round-trip)" value={fmtNum(math.costAmount, 0) + ' €'} />
          <Stat label="Size ¼-Kelly (dimostrata)" value={kellySize != null ? fmtNum(kellySize, 2) : `in raccolta dati: n=${kelly.n || 0}/${MIN_SAMPLE}`} cls={kellySize != null ? 'pos' : ''} />
        </div>
        {kellySize != null && size > 0 && kellySize < size && (
          <p className="muted small kelly-inline">La size dal rischio% ({fmtNum(size, 2)}) è oltre la ¼-Kelly dimostrata ({fmtNum(kellySize, 2)}): il tuo edge misurato suggerisce di scommettere meno.</p>
        )}
      </section>

      {/* 1) MARKET ODDS ON YOUR LEVELS */}
      <section className="panel">
        <header className="panel-head">
          <h2>1 · Odds del mercato sui TUOI livelli <InfoTip text={DH.implied_prob.text} label={DH.implied_prob.label} /></h2>
          <span className="muted small">odds risk-neutral dalle opzioni · non una previsione</span>
        </header>
        {implied.probTarget == null ? <p className="muted small">Probabilità implicite non disponibili per {f.symbol}.</p> : (
          <>
            <div className="stat-grid">
              <Stat label={`Prob. tocca il target (${target != null ? fmtNum(target, 2) : '—'})`} value={pct(implied.probTarget)} cls="pos" />
              <Stat label={`Prob. tocca lo stop (${stop != null ? fmtNum(stop, 2) : '—'})`} value={pct(implied.probStop)} cls="neg" />
            </div>
            <p className="muted small">{implied.note} <em>Approssimazione: prob a scadenza, non first-touch (la prob di TOCCARE prima è più alta).</em></p>
          </>
        )}
      </section>

      {/* 2) EVENT RISK IN THE WINDOW */}
      <section className="panel">
        <header className="panel-head"><h2>2 · Rischio-evento nella finestra ({horizon}g)</h2></header>
        {board?.event_risk && (
          <p className="gate-line gate-warn"><span className="gate-tag">⚑ imminente</span>
            <strong>{board.event_risk.title}</strong> tra {countdown(board.event_risk.event_time, nowMs)}
            {board.event_risk.expected_move_pct != null && <> · movimento atteso ±{fmtNum(board.event_risk.expected_move_pct, 1)}%</>}</p>
        )}
        {eventsInWindow.length === 0 ? <p className="muted small">Nessun evento rilevante entro l’orizzonte.</p> : (
          <ul className="tight">{eventsInWindow.map((e, i) => (
            <li key={i}><strong>{e.title}</strong> <span className="muted small">{String(e.event_time).slice(0, 16)} · tra {countdown(e.event_time, nowMs)}</span></li>
          ))}</ul>
        )}
      </section>

      {/* 3) THE BET MATH */}
      <section className="panel">
        <header className="panel-head"><h2>3 · Matematica della scommessa <InfoTip text={DH.breakeven_winrate.text} label={DH.breakeven_winrate.label} /></h2></header>
        <div className="stat-grid">
          <Stat label="R/R" value={math.rr == null ? '—' : `${math.rr.toFixed(2)}R`} />
          <Stat label="Rischio €" value={math.riskAmount == null ? '—' : fmtNum(math.riskAmount, 0)} />
          <Stat label="Reward €" value={math.rewardAmount == null ? '—' : fmtNum(math.rewardAmount, 0)} />
          <Stat label="Win-rate di pareggio (costi incl.)" value={pct(math.breakevenWinrate)} cls="warn" />
          <Stat label="…senza costi" value={pct(math.breakevenWinrateNoCost)} />
        </div>
        <div className={`bench-verdict ${theVerdict.edge == null ? '' : theVerdict.edge > 0 ? 'edge-pos' : 'edge-neg'}`}>
          <p>{theVerdict.text}</p>
          {theVerdict.disclaimer && <p className="muted small">{theVerdict.disclaimer}</p>}
        </div>
      </section>

      {/* 4) STRUCTURE COMPARISON */}
      <section className="panel">
        <header className="panel-head"><h2>4 · Confronto di struttura</h2><span className="muted small">diretta con stop vs opzione a rischio definito</span></header>
        <div className="lens-grid">
          <div className="lens-card">
            <span className="lens-tag">Diretta (CFD/spot) + stop</span>
            <p>Perdita se stop colpito: <strong>{math.riskAmount == null ? '—' : fmtNum(math.riskAmount, 0) + ' €'}</strong>. R/R {math.rr == null ? '—' : math.rr.toFixed(2)}.
              <br /><span className="neg">Contro:</span> <strong>gap risk</strong> — un salto oltre lo stop perde di più del previsto (vedi scenari).</p>
          </div>
          <div className="lens-card">
            <span className="lens-tag">Opzione a rischio definito</span>
            {option ? (
              <p>Long {option.kind}: perdita max = premio <strong>{fmtNum(option.premium, 2)}</strong> (×{multiplier} = {fmtNum(option.maxLoss * multiplier, 0)} €).
                POP {pct(option.pop)}, R/R al target {option.rrToTarget == null ? '—' : option.rrToTarget.toFixed(2)}, theta {fmtNum(option.thetaDaily, 3)}/g.
                <br /><span className="neg">Contro:</span> paghi il <strong>premio</strong> (theta) e nessun gap risk.
                <br /><span className="muted small">{option.note}</span></p>
            ) : <p className="muted small">IV implicita non disponibile per l’illustrazione opzione.</p>}
          </div>
        </div>
      </section>

      {/* 5) SCENARIO LADDER */}
      <section className="panel">
        <header className="panel-head"><h2>5 · Scala di scenari (P&L in €)</h2></header>
        {ladder.length === 0 ? <p className="muted small">Inserisci entry/stop/target (e serve l’ATR dal board).</p> : (
          <div className="risk-table-wrap"><table className="risk-table">
            <thead><tr><th>Scenario</th><th>Prezzo</th><th>P&L €</th></tr></thead>
            <tbody>{ladder.map((row, i) => (
              <tr key={i} className={row.kind === 'gap' ? 'excluded' : ''}>
                <td>{row.label}{row.kind === 'gap' ? ' ⚠' : ''}</td>
                <td>{fmtNum(row.price, 2)}</td>
                <td className={row.pnl >= 0 ? 'pos' : 'neg'}>{fmtNum(row.pnl, 0)}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
        <p className="muted small caveat">P&L col point value reale (×{multiplier}) e la size dal rischio%. «gap oltre lo stop» = worst case della via diretta.</p>
      </section>

      {/* 6) INTEGRATED GATE + MONITOR AS TEST */}
      <section className="panel">
        <header className="panel-head"><h2>6 · Gate & test</h2><span className="muted small">disciplina e rischio · nessun ordine</span></header>
        <BudgetStrip caps={caps} used={budgetUsed} setAside={setAsideToday(closedPositions, Number(settings?.set_aside_per_day ?? 100))} />
        <GateWarnings warnings={size > 0 ? gate.warnings : gate.warnings.filter((w) => w.severity !== 'info')} okWhenEmpty={size > 0} />
        <div className="form-actions">
          <button className="primary" onClick={monitorTest} disabled={saving || stop == null}>{saving ? 'Salvo…' : '🧪 Monitora come test'}</button>
          {status && <span className={status.type === 'ok' ? 'ok' : 'error'}>{status.msg}</span>}
        </div>
        <p className="muted small">Precompila la paper con QUESTA scommessa e salva lo snapshot (win-rate di pareggio + odds impliciti) per la review. Niente ordini.</p>
      </section>
      {/* "Confronta strumenti" rimosso (AUDIT §6): la Panoramica in MERCATI è l'unica
          tabella multi-strumento, stesso scopo. */}
    </div>
  )
}

const pct = (v) => (v == null ? '—' : fmtPct(v * 100).replace('+', ''))
function Stat({ label, value, cls = '' }) {
  return <div className="stat"><span className="stat-label">{label}</span><span className={`stat-value ${cls}`}>{value}</span></div>
}

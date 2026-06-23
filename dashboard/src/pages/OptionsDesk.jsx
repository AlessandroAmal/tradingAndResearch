import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchOptionUnderlyings,
  fetchOptionExpiries,
  fetchOptionChain,
  fetchHedgeProposals,
} from '../api/data'
import {
  approxSpot,
  payoffCurve,
  probabilityOfProfit,
  singleLeg,
  verticalSpread,
  yearsTo,
} from '../lib/options'
import { fmtNum, fmtPct } from '../lib/format'
import PayoffChart from '../components/PayoffChart'

// Desk-configured risk-free rate (mirrors config options.risk_free_rate).
// Used only for the implied (risk-neutral) probability display.
const RFR = 0.04

// Options / insurance desk — analysis only, never an order. The desk works on
// the underlyings the worker fetched (see the architecture note in the README:
// on-demand any-underlying recompute would need a backend endpoint).
export default function OptionsDesk() {
  const [tab, setTab] = useState('chain')
  const [underlyings, setUnderlyings] = useState([])
  const [underlying, setUnderlying] = useState('')
  const [expiries, setExpiries] = useState([])
  const [expiry, setExpiry] = useState('')
  const [chain, setChain] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchOptionUnderlyings().then(({ data, error }) => {
      if (error) { setError(error.message); return }
      setUnderlyings(data || [])
      if (data?.length) setUnderlying(data[0])
    })
  }, [])

  useEffect(() => {
    if (!underlying) return
    fetchOptionExpiries(underlying).then(({ data }) => {
      setExpiries(data || [])
      setExpiry(data?.[0] || '')
    })
  }, [underlying])

  useEffect(() => {
    if (!underlying || !expiry) { setChain([]); return }
    fetchOptionChain(underlying, expiry).then(({ data, error }) => {
      if (error) setError(error.message)
      setChain(data || [])
    })
  }, [underlying, expiry])

  const spot = useMemo(() => approxSpot(chain), [chain])

  return (
    <div className="desk">
      <section className="panel">
        <header className="panel-head">
          <h2>Options desk</h2>
          <span className="muted small">analysis &amp; proposals · places nothing</span>
        </header>

        {error && <p className="error">Options data unavailable — {error}</p>}
        {underlyings.length === 0 && !error && (
          <p className="muted small">No option chains yet. Run <code>python -m app.main options</code>.</p>
        )}

        <div className="desk-controls">
          <label>Underlying
            <select value={underlying} onChange={(e) => setUnderlying(e.target.value)}>
              {underlyings.map((u) => <option key={u} value={u}>{u}</option>)}
            </select>
          </label>
          <label>Expiry
            <select value={expiry} onChange={(e) => setExpiry(e.target.value)}>
              {expiries.map((x) => <option key={x} value={x}>{x}</option>)}
            </select>
          </label>
          {spot != null && <span className="chip">≈ spot {fmtNum(spot, 2)}</span>}
        </div>

        <nav className="nav desk-tabs">
          {['chain', 'insurance', 'directional'].map((t) => (
            <button key={t} className={`nav-btn ${tab === t ? 'active' : ''}`}
              onClick={() => setTab(t)}>{t}</button>
          ))}
        </nav>
      </section>

      {tab === 'chain' && <ChainTab chain={chain} />}
      {tab === 'directional' && (
        <DirectionalTab chain={chain} spot={spot} expiry={expiry} />
      )}
      {tab === 'insurance' && <InsuranceTab />}
    </div>
  )
}

function ChainTab({ chain }) {
  if (!chain.length) return <section className="panel"><p className="muted small">No chain for this selection.</p></section>
  return (
    <section className="panel">
      <header className="panel-head"><h2>Chain (recomputed IV &amp; Greeks)</h2></header>
      <div className="risk-table-wrap">
        <table className="risk-table">
          <thead><tr>
            <th>Strike</th><th>Type</th><th>Bid/Ask</th><th>IV</th>
            <th>Δ</th><th>Γ</th><th>Θ</th><th>Vega</th><th>Vol/OI</th>
          </tr></thead>
          <tbody>
            {chain.map((c, i) => (
              <tr key={`${c.strike}-${c.option_type}-${i}`}>
                <td>{fmtNum(c.strike, 2)}</td>
                <td><span className={`badge ${c.option_type === 'call' ? 'long' : 'short'}`}>{c.option_type}</span></td>
                <td className="muted">{fmtNum(c.bid, 2)}/{fmtNum(c.ask, 2)}</td>
                <td>{c.implied_vol != null ? fmtPct(c.implied_vol * 100) : '—'}</td>
                <td>{fmtNum(c.delta, 2)}</td>
                <td>{fmtNum(c.gamma, 4)}</td>
                <td>{fmtNum(c.theta, 1)}</td>
                <td>{fmtNum(c.vega, 1)}</td>
                <td className="muted small">{fmtNum(c.volume, 0)}/{fmtNum(c.open_interest, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function DirectionalTab({ chain, spot, expiry }) {
  const [kind, setKind] = useState('single') // single | vertical
  const [optionType, setOptionType] = useState('call')
  const [side, setSide] = useState('long')
  const [longStrike, setLongStrike] = useState('')
  const [shortStrike, setShortStrike] = useState('')

  const strikes = useMemo(
    () => [...new Set(chain.filter((c) => c.option_type === optionType).map((c) => c.strike))]
      .sort((a, b) => a - b),
    [chain, optionType],
  )
  const mid = (strike) => {
    const row = chain.find((c) => c.option_type === optionType && c.strike === Number(strike))
    return row?.mid ?? row?.last ?? null
  }
  const ivAt = (strike) => {
    const row = chain.find((c) => c.option_type === optionType && c.strike === Number(strike))
    return row?.implied_vol ?? null
  }

  let metrics = null
  let sigma = null
  if (kind === 'single' && longStrike && mid(longStrike) != null) {
    metrics = singleLeg(optionType, side, Number(longStrike), mid(longStrike))
    sigma = ivAt(longStrike)
  } else if (kind === 'vertical' && longStrike && shortStrike && mid(longStrike) != null && mid(shortStrike) != null) {
    metrics = verticalSpread(optionType, Number(longStrike), mid(longStrike), Number(shortStrike), mid(shortStrike))
    sigma = ivAt(longStrike)
  }

  const T = expiry ? yearsTo(expiry) : 0
  const pop = metrics && spot && sigma ? probabilityOfProfit(metrics, spot, T, RFR, sigma) : null
  const curve = metrics && spot ? payoffCurve(metrics.legs, spot * 0.8, spot * 1.2, 60) : []

  return (
    <section className="panel">
      <header className="panel-head"><h2>Directional builder</h2></header>
      <div className="desk-controls">
        <label>Structure
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="single">single leg</option>
            <option value="vertical">vertical spread</option>
          </select></label>
        <label>Type
          <select value={optionType} onChange={(e) => setOptionType(e.target.value)}>
            <option value="call">call</option><option value="put">put</option>
          </select></label>
        {kind === 'single' && (
          <label>Side
            <select value={side} onChange={(e) => setSide(e.target.value)}>
              <option value="long">long</option><option value="short">short</option>
            </select></label>
        )}
        <label>{kind === 'vertical' ? 'Long strike' : 'Strike'}
          <select value={longStrike} onChange={(e) => setLongStrike(e.target.value)}>
            <option value="">—</option>
            {strikes.map((s) => <option key={s} value={s}>{s}</option>)}
          </select></label>
        {kind === 'vertical' && (
          <label>Short strike
            <select value={shortStrike} onChange={(e) => setShortStrike(e.target.value)}>
              <option value="">—</option>
              {strikes.map((s) => <option key={s} value={s}>{s}</option>)}
            </select></label>
        )}
      </div>

      {metrics ? (
        <>
          <div className="stat-grid">
            <Stat label="Max loss" value={metrics.maxLoss == null ? '∞' : fmtNum(metrics.maxLoss, 2)} />
            <Stat label="Max gain" value={metrics.maxGain == null ? '∞' : fmtNum(metrics.maxGain, 2)} />
            <Stat label="Breakeven" value={fmtNum(metrics.breakeven, 2)} />
            <Stat label="POP (implied)" value={pop == null ? '—' : fmtPct(pop * 100)} />
          </div>
          <PayoffChart curve={curve} breakeven={metrics.breakeven} />
          <p className="muted small">
            POP is the risk-neutral probability implied by option prices (uses spot≈{fmtNum(spot, 1)},
            IV {sigma != null ? fmtPct(sigma * 100) : '—'}, r {RFR}). Not a forecast.
          </p>
        </>
      ) : (
        <p className="muted small">Pick strike(s) to see max loss / R-R / breakeven / POP and payoff.</p>
      )}
    </section>
  )
}

function InsuranceTab() {
  const [proposals, setProposals] = useState([])
  const [selId, setSelId] = useState('')
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    fetchHedgeProposals().then(({ data, error }) => {
      if (error) setError(error.message)
      setProposals(data || [])
      if (data?.length) setSelId(data[0].id)
    })
  }, [])
  useEffect(() => { load() }, [load])

  const sel = proposals.find((p) => p.id === selId)
  const curve = sel?.legs && sel.spot
    ? payoffCurve(sel.legs, sel.spot * 0.7, sel.spot * 1.3, 60)
    : []

  return (
    <section className="panel">
      <header className="panel-head"><h2>Insurance — proposed hedges</h2></header>
      {error && <p className="error">Hedge proposals unavailable — {error}</p>}
      {proposals.length === 0 && !error && (
        <p className="muted small">No proposals yet. Run <code>python -m app.main options</code> (needs holdings).</p>
      )}

      {proposals.length > 0 && (
        <label className="desk-controls">Holding hedge
          <select value={selId} onChange={(e) => setSelId(e.target.value)}>
            {proposals.map((p) => (
              <option key={p.id} value={p.id}>{p.symbol} · {p.kind} · {p.expiry}</option>
            ))}
          </select>
        </label>
      )}

      {sel && (
        <>
          <div className="stat-grid">
            <Stat label="Net cost" value={fmtNum(sel.cost, 2)} />
            <Stat label="Floor (protected)" value={fmtNum(sel.floor, 2)} />
            <Stat label="Breakeven" value={fmtNum(sel.breakeven, 2)} />
            <Stat label={sel.kind === 'collar' ? 'Cap' : '% covered'}
              value={sel.kind === 'collar' ? fmtNum(sel.max_gain, 2) : (sel.pct_covered != null ? fmtPct(sel.pct_covered) : '—')} />
          </div>
          <PayoffChart curve={curve} breakeven={sel.breakeven} />
          {sel.note && <p className="muted small">{sel.note}</p>}
        </>
      )}
    </section>
  )
}

function Stat({ label, value }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
    </div>
  )
}

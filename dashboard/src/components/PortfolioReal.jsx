import { Fragment, useCallback, useEffect, useMemo, useState } from 'react'
import { fetchHoldings, fetchPrices } from '../api/data'
import { resolveIsin, saveHolding, deleteHoldingApi, editHolding, checkPlausibility, verifyHoldings, apiConfigured } from '../api/control'
import { valueRow, byCategory, rateAtDate } from '../lib/portfolio'
import { themeConcentration, themesBySymbol } from '../lib/concentration'
import { fmtNum, fmtPct } from '../lib/format'
import PositionsTable from './PositionsTable'

const EUR_PAIRS = { USD: 'EURUSD=X', GBP: 'EURGBP=X', CHF: 'EURCHF=X', DKK: 'EURDKK=X', JPY: 'EURJPY=X', HKD: 'EURHKD=X' }
const BASE = 'EUR'
const SUB = 'Portafogli Figli'
const eur = (v) => (v == null ? 'n/d' : `€${fmtNum(v, 2)}`)
const eur0 = (v) => (v == null ? 'n/d' : `€${fmtNum(v, 0)}`)

// PORTAFOGLIO REALE — the long book by ISIN/CSV: valued live (native + EUR), with
// categories, manual-valued items (icon, no price feed), closed history, a
// mortgage as a negative liability, and "Portafogli Figli" as a distinct
// sub-portfolio. READ-ONLY: nothing here places an order.
export default function PortfolioReal({ instruments = [], priceBySymbol = {}, onOpenAsset,
                                       positions = [], multiplierBySymbol = {}, settings = null, nowMs = Date.now() }) {
  // Single portfolio view with a long-book vs trade filter (§6.A #3): the long
  // book (holdings) is the structural portfolio; trades are the tactical ≤3wk book.
  const [view, setView] = useState('long')   // long | trade | all
  const [holdings, setHoldings] = useState([])
  const [fxSeries, setFxSeries] = useState({})
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    const { data } = await fetchHoldings()
    setHoldings((data || []).filter((h) => Number(h.quantity) !== 0 || h.valuation_mode === 'manual' || h.manual_value != null))
    setLoading(false)
  }, [])
  useEffect(() => { load() }, [load])

  const instById = useMemo(() => Object.fromEntries(instruments.map((i) => [i.id, i])), [instruments])
  // pricing symbol: the real instrument via instrument_id (display symbol may be
  // de-duplicated for a second tranche), else the holding's own symbol.
  const priceSymbolFor = useCallback((h) => instById[h.instrument_id]?.symbol || h.symbol, [instById])
  const currencyFor = useCallback((h) => (h.currency || instById[h.instrument_id]?.currency || BASE).toUpperCase(), [instById])

  // FX history for buy-date conversion of every non-EUR currency present.
  useEffect(() => {
    const curSet = new Set(holdings.map(currencyFor).filter((c) => c !== BASE && EUR_PAIRS[c]))
    const idBySymbol = Object.fromEntries(instruments.map((i) => [i.symbol, i.id]))
    let alive = true
    Promise.all([...curSet].map(async (c) => {
      const pair = EUR_PAIRS[c]; const id = idBySymbol[pair]
      if (!id) return [pair, []]
      const { data } = await fetchPrices(id, 2500)
      return [pair, (data || []).slice().reverse().map((r) => ({ ts: r.ts, close: r.close }))]
    })).then((pairs) => { if (alive) setFxSeries(Object.fromEntries(pairs)) })
    return () => { alive = false }
  }, [holdings, instruments, currencyFor])

  const rateNowFor = useCallback((cur) => {
    if (cur === BASE) return 1
    const pair = EUR_PAIRS[cur]
    return pair ? (priceBySymbol[pair] ?? null) : null
  }, [priceBySymbol])

  const valued = useMemo(() => holdings.map((h) => {
    const cur = currencyFor(h)
    const price = priceBySymbol[priceSymbolFor(h)] ?? null
    const rateNow = rateNowFor(cur)
    const pair = EUR_PAIRS[cur]
    const rateBuy = cur === BASE ? 1 : (pair && h.buy_date ? rateAtDate(fxSeries[pair], h.buy_date) : null)
    return { ...valueRow({ ...h, currency: cur }, price, rateNow, rateBuy), h, ticker: priceSymbolFor(h) }
  }), [holdings, priceBySymbol, fxSeries, currencyFor, priceSymbolFor, rateNowFor])

  const grouped = useMemo(() => byCategory(valued, { subPortfolioNames: [SUB] }), [valued])
  const closed = useMemo(() => valued.filter((v) => v.closed), [valued])
  // Thematic concentration computed ONCE, on ONE base (§6.A #3): the EUR VALUE of
  // the real long-book holdings. This is the correct base — it's the money you
  // actually hold exposed to a theme — vs the old trade-book base (size×prezzo×
  // point-value) which mixed native currencies and double-counted transient trades.
  const concentration = useMemo(() => {
    const bySym = themesBySymbol(instruments)
    const pos = valued.filter((v) => !v.closed && !v.manual && v.valueEur != null)
      .map((v) => ({ symbol: v.ticker, notional: v.valueEur }))
    return themeConcentration(pos, bySym).filter((t) => t.concentrated)
  }, [valued, instruments])

  const [editId, setEditId] = useState(null)   // holding id being edited (shared)
  const showLong = view !== 'trade'
  const showTrade = view !== 'long'
  const btn = (k, label) => (
    <button key={k} className={`nav-btn ${view === k ? 'active' : ''}`} onClick={() => setView(k)}>{label}</button>
  )

  return (
    <div className="desk">
      <nav className="nav subnav" aria-label="Vista portafoglio">
        {btn('long', 'Long book (holdings)')}{btn('trade', 'Trade (≤3 sett.)')}{btn('all', 'Tutto')}
      </nav>
      {showLong && <PatrimonySummary grouped={grouped} concentration={concentration} loading={loading} />}
      {showLong && <PlausibilityPanel onEdit={setEditId} onChanged={load} />}
      {showLong && Object.values(grouped.cats).sort((a, b) => (a.isSub - b.isSub) || (b.valueEur - a.valueEur)).map((c) => (
        <CategoryTable key={c.category} cat={c} editId={editId} setEditId={setEditId} onOpenAsset={onOpenAsset} onChanged={load} />
      ))}
      {showLong && closed.length > 0 && <ClosedSection rows={closed} />}
      {showTrade && (
        <section className="panel">
          <header className="panel-head">
            <h2>Posizioni di trading (reali, ≤3 settimane)</h2>
            <span className="muted small">heat, stop, R · il libro tattico, distinto dal long book</span>
          </header>
          <PositionsTable positions={positions} priceBySymbol={priceBySymbol} multiplierBySymbol={multiplierBySymbol} settings={settings} nowMs={nowMs} />
        </section>
      )}
      {showLong && <HoldingForm instruments={instruments} onSaved={load} />}
    </div>
  )
}

// Plausibility of the declared cost vs the market price on the buy date.
function PlausibilityPanel({ onEdit, onChanged }) {
  const [res, setRes] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const run = async () => {
    setBusy(true); setErr(null)
    const { data, error } = await checkPlausibility()
    setBusy(false)
    if (error) { setErr(error.message); return }
    setRes(data)
  }
  const verify = async (ids) => {
    if (!ids.length) return
    setBusy(true); await verifyHoldings(ids); setBusy(false)
    onChanged?.(); run()
  }
  if (!apiConfigured) return null
  const results = res?.results || []
  const suspects = results.filter((r) => r.status === 'sospetta')
  const unver = results.filter((r) => r.status === 'non_verificabile')
  const plausToVerify = results.filter((r) => r.status === 'plausibile' && r.needs_review)
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Controllo di plausibilità del carico</h2>
        <span className="muted small">carico dichiarato vs prezzo di mercato alla data d'acquisto</span>
      </header>
      {!res ? (
        <button className="ghost small" disabled={busy} onClick={run}>{busy ? 'Controllo… (può richiedere ~1 min)' : '🔍 Controlla plausibilità'}</button>
      ) : (
        <>
          <div className="stat-grid">
            <div className="stat"><span className="stat-label">Plausibili (±{Math.round(res.threshold * 100)}%)</span><span className="stat-value pos">{res.summary.plausibile}</span></div>
            <div className="stat"><span className="stat-label">Sospette</span><span className="stat-value neg">{res.summary.sospetta}</span></div>
            <div className="stat"><span className="stat-label">Non verificabili</span><span className="stat-value muted">{res.summary.non_verificabile}</span></div>
          </div>
          {plausToVerify.length > 0 && (
            <div className="form-actions">
              <button className="primary" disabled={busy} onClick={() => verify(plausToVerify.map((r) => r.id))}>✓ Segna le {plausToVerify.length} plausibili (ancora da verificare) come Verificato</button>
            </div>
          )}
          {suspects.length > 0 && (
            <div className="risk-table-wrap">
              <table className="risk-table">
                <thead><tr><th>Strumento</th><th>Data</th><th>Carico dich.</th><th>Mercato quel giorno</th><th>Scarto</th><th></th></tr></thead>
                <tbody>
                  {suspects.map((r) => (
                    <tr key={r.id} className="review-row">
                      <td>{r.name || r.symbol}<br /><span className="muted small">{r.symbol}</span></td>
                      <td className="muted small">{r.buy_date}</td>
                      <td>€{fmtNum(r.declared_eur, 2)}</td>
                      <td>€{fmtNum(r.market_eur, 2)}</td>
                      <td className="neg">{fmtPct(r.deviation_pct * 100)}</td>
                      <td><span className="flags">
                        <button className="flag-badge" disabled={busy} onClick={() => verify([r.id])}>conferma comunque</button>
                        <button className="flag-badge" onClick={() => onEdit?.(r.id)}>modifica</button>
                      </span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {unver.length > 0 && <p className="muted small">Non verificabili ({unver.length}): {unver.map((r) => `${r.symbol} — ${r.reason}`).join(' · ')}</p>}
          <button className="ghost small" disabled={busy} onClick={run}>{busy ? '…' : '↻ Ricontrolla'}</button>
        </>
      )}
      {err && <p className="error">{err}</p>}
      <p className="muted small caveat">Controllo di plausibilità contro il prezzo di mercato alla data dichiarata — non sostituisce l'estratto conto; carichi medi da più tranche possono divergere legittimamente.</p>
    </section>
  )
}

function PatrimonySummary({ grouped, concentration, loading }) {
  const { main, sub, cats } = grouped
  const liabilities = Object.values(cats).flatMap((c) => c.rows).filter((r) => r.isLiability && r.valueEur != null)
  const liabTot = liabilities.reduce((s, r) => s + r.valueEur, 0)
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Patrimonio reale</h2>
        <span className="muted small">valore live · categorie · mercato vs manuale · passività · sotto-portafogli</span>
      </header>
      <div className="stat-grid">
        <div className="stat"><span className="stat-label">Patrimonio principale (EUR)</span><span className="stat-value">{eur0(main.valueEur)}</span></div>
        <div className="stat"><span className="stat-label">di cui a mercato</span><span className="stat-value">{eur0(main.market)}</span></div>
        <div className="stat"><span className="stat-label">di cui manuale</span><span className="stat-value">{eur0(main.manual)}</span></div>
        {liabTot < 0 && <div className="stat"><span className="stat-label">di cui passività</span><span className="stat-value neg">{eur0(liabTot)}</span></div>}
        <div className="stat"><span className="stat-label">Portafogli Figli (a parte)</span><span className="stat-value">{eur0(sub.valueEur)}</span></div>
      </div>
      {loading && <p className="muted small">Carico…</p>}
      {concentration.length > 0 && (
        <div className="conc-block">
          {concentration.map((t) => (
            <p key={t.theme} className="gate-line gate-warn">
              <span className="gate-tag">⚠ {t.label}</span>
              <strong>{t.positions} titoli</strong> sullo stesso tema{t.weight != null ? <> ({fmtPct(t.weight * 100).replace('+', '')} del book a mercato)</> : null}: {t.symbols.join(', ')} — correlati, scendono INSIEME.
            </p>
          ))}
        </div>
      )}
      <p className="honest-note small">Le holdings NON entrano nell'heat del rischio di trading. «Valore manuale» ✋ = inserito a mano (oro fisico, casa, mutuo, fondi pensione, TFR, obbligazioni singole), nessun prezzo scaricato. Il mutuo è una passività (negativa). Dati mancanti = n/d, mai stimati.</p>
    </section>
  )
}

function CategoryTable({ cat, editId, setEditId, onOpenAsset, onChanged }) {
  const [confirmDel, setConfirmDel] = useState(null)
  const editing = editId; const setEditing = setEditId   // shared with the plausibility panel
  const [busy, setBusy] = useState(false)
  const del = async (symbol) => { setBusy(true); await deleteHoldingApi(symbol); setBusy(false); setConfirmDel(null); onChanged?.() }
  const rows = cat.rows.filter((r) => !r.closed)
  if (rows.length === 0) return null
  const needsReview = (h) => (h.needs_review != null ? h.needs_review : /verifica/i.test(h.note || ''))
  return (
    <section className="panel">
      <header className="panel-head">
        <h2>{cat.category}{cat.isSub && <span className="chip" style={{ marginLeft: 8 }}>sotto-portafoglio</span>}</h2>
        <span className="muted small">{eur0(cat.valueEur)} · mercato {eur0(cat.market)} · manuale {eur0(cat.manual)}{cat.nd ? ` · n/d ${cat.nd}` : ''}</span>
      </header>
      <div className="risk-table-wrap">
        <table className="risk-table">
          <thead><tr>
            <th>Strumento</th><th>Qtà</th><th>Carico</th><th>Prezzo</th><th>Val. nativo</th><th>Val. EUR</th><th>P&L (prezzo/cambio)</th><th></th>
          </tr></thead>
          <tbody>
            {rows.map((v) => {
              const h = v.h; const verif = needsReview(h)
              return (
                <Fragment key={h.id}>
                <tr className={`${v.isLiability ? 'neg-row' : ''} ${verif ? 'review-row' : ''}`}>
                  <td>
                    {v.manual
                      ? <span title="valore manuale">✋ {h.name}</span>
                      : <button className="linklike" onClick={() => onOpenAsset?.(v.ticker)} title="Apri in ASSET">{h.name}</button>}
                    <br /><span className="muted small">{v.manual ? (h.isin || 'manuale') : v.ticker}{v.currency ? ` · ${v.currency}` : ''}{verif && <span className="warn"> · ⚠ VERIFICARE</span>}</span>
                  </td>
                  <td className="muted">{v.manual ? '—' : fmtNum(v.quantity, 2)}</td>
                  <td className="muted">{v.avgPrice == null ? '—' : fmtNum(v.avgPrice, 2)}</td>
                  <td>{v.manual ? <span className="muted">manuale</span> : (v.price == null ? <span className="muted">n/d</span> : fmtNum(v.price, 2))}</td>
                  <td className="muted">{v.manual ? '—' : (v.valueNative == null ? 'n/d' : fmtNum(v.valueNative, 2))}</td>
                  <td className={v.isLiability ? 'neg' : ''}>{eur(v.valueEur)}</td>
                  <td className="muted small">
                    {v.manual ? '—' : (
                      <>
                        <span className={v.pnlAbsEur == null ? 'muted' : v.pnlAbsEur >= 0 ? 'pos' : 'neg'}>{v.pnlAbsEur == null ? 'n/d' : `${v.pnlAbsEur >= 0 ? '+' : ''}${eur0(v.pnlAbsEur)}`}</span>
                        {' ('}
                        <span className={v.pnlPriceEur == null ? 'muted' : v.pnlPriceEur >= 0 ? 'pos' : 'neg'}>{v.pnlPriceEur == null ? 'n/d' : eur0(v.pnlPriceEur)}</span>/
                        <span className={v.pnlFxEur == null ? 'muted' : v.pnlFxEur >= 0 ? 'pos' : 'neg'}>{v.pnlFxEur == null ? 'n/d' : eur0(v.pnlFxEur)}</span>
                        {')'}
                      </>
                    )}
                  </td>
                  <td>
                    <span className="flags">
                      <button className="flag-badge" onClick={() => setEditing(editing === h.id ? null : h.id)} title="Modifica">✎</button>
                      {confirmDel === h.symbol ? (
                        <><button className="flag-badge bad" disabled={busy} onClick={() => del(h.symbol)}>conferma</button><button className="flag-badge" onClick={() => setConfirmDel(null)}>no</button></>
                      ) : <button className="flag-badge" onClick={() => setConfirmDel(h.symbol)} title="Rimuovi">✕</button>}
                    </span>
                  </td>
                </tr>
                {editing === h.id && (
                  <tr><td colSpan={8}><EditForm v={v} needsReview={verif} onDone={() => { setEditing(null); onChanged?.() }} onCancel={() => setEditing(null)} /></td></tr>
                )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}

// Inline edit: quantity / carico / valuta / data / ticker (if ISIN resolution was
// wrong) / nota, plus a "verificato" toggle that clears the review flag.
function EditForm({ v, needsReview, onDone, onCancel }) {
  const h = v.h
  const [qty, setQty] = useState(v.manual ? (h.quantity ?? '') : (h.quantity ?? ''))
  const [avg, setAvg] = useState(h.avg_price ?? '')
  const [avgCur, setAvgCur] = useState((h.avg_price_currency || 'EUR').toUpperCase())
  const [cur, setCur] = useState(v.currency || '')
  const [buyDate, setBuyDate] = useState(h.buy_date || '')
  const [note, setNote] = useState(h.note || '')
  const [ticker, setTicker] = useState('')
  const [verified, setVerified] = useState(!needsReview)
  const [busy, setBusy] = useState(false); const [err, setErr] = useState(null)
  const save = async () => {
    setBusy(true); setErr(null)
    const payload = { id: h.id, note, needs_review: !verified }
    if (qty !== '') payload.quantity = Number(qty)
    if (avg !== '') payload.avg_price = Number(avg)
    if (avgCur) payload.avg_price_currency = avgCur
    if (cur) payload.currency = cur.toUpperCase()
    if (buyDate) payload.buy_date = buyDate
    if (ticker.trim()) { payload.ticker = ticker.trim(); payload.isin = h.isin || null }
    const { error } = await editHolding(payload)
    setBusy(false)
    if (error) { setErr(error.message); return }
    onDone?.()
  }
  return (
    <div className="resolved-box">
      <p className="muted small">Modifica «{h.name}» {v.manual ? '(valore manuale)' : `· ticker attuale ${v.ticker}`}</p>
      <div className="paper-fields">
        <label>{v.manual ? 'Valore/qtà' : 'Quantità'}<input type="number" step="any" value={qty} onChange={(e) => setQty(e.target.value)} /></label>
        <label>{v.manual ? 'Valore unitario (EUR)' : `Prezzo di carico (in ${avgCur})`}<input type="number" step="any" value={avg} onChange={(e) => setAvg(e.target.value)} /></label>
        {!v.manual && <label>Valuta del carico<select value={avgCur} onChange={(e) => setAvgCur(e.target.value)}><option value="EUR">EUR (di conto)</option>{v.currency && v.currency !== 'EUR' && <option value={v.currency}>{v.currency} (di quotazione)</option>}</select></label>}
        {!v.manual && <label>Valuta quotazione<input value={cur} onChange={(e) => setCur(e.target.value)} placeholder="USD/EUR/…" /></label>}
        {!v.manual && <label>Data acquisto<input type="date" value={buyDate} onChange={(e) => setBuyDate(e.target.value)} /></label>}
        {!v.manual && <label>Ticker (se ISIN sbagliato)<input value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder={v.ticker} /></label>}
        <label>Note<input value={note} onChange={(e) => setNote(e.target.value)} /></label>
      </div>
      <label className="verify-toggle"><input type="checkbox" checked={verified} onChange={(e) => setVerified(e.target.checked)} /> Verificato (togli l'avviso ⚠)</label>
      <div className="form-actions">
        <button className="primary" disabled={busy} onClick={save}>{busy ? 'Salvo…' : '✓ Salva modifiche'}</button>
        <button className="ghost small" disabled={busy} onClick={onCancel}>Annulla</button>
      </div>
      {err && <p className="error">{err}</p>}
    </div>
  )
}

function ClosedSection({ rows }) {
  return (
    <section className="panel">
      <header className="panel-head"><h2>Storico (posizioni chiuse)</h2><span className="muted small">non contano nel patrimonio attuale</span></header>
      <div className="risk-table-wrap">
        <table className="risk-table">
          <thead><tr><th>Strumento</th><th>Categoria</th><th>Qtà</th><th>Carico</th><th>Nota</th></tr></thead>
          <tbody>{rows.map((v) => (
            <tr key={v.h.id} className="excluded">
              <td>{v.h.name}<br /><span className="muted small">{v.ticker}</span></td>
              <td className="muted small">{v.category}</td>
              <td className="muted">{fmtNum(v.quantity, 2)}</td>
              <td className="muted">{v.avgPrice == null ? '—' : fmtNum(v.avgPrice, 2)}</td>
              <td className="muted small">{v.h.note || '—'}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  )
}

// ISIN/ticker → resolve → confirm name+currency → save one holding.
function HoldingForm({ instruments, onSaved }) {
  const [query, setQuery] = useState('')
  const [resolving, setResolving] = useState(false)
  const [resolved, setResolved] = useState(null)
  const [candidates, setCandidates] = useState([])
  const [manual, setManual] = useState(false)
  const [qty, setQty] = useState(''); const [avg, setAvg] = useState(''); const [avgCur, setAvgCur] = useState('EUR')
  const [buyDate, setBuyDate] = useState(''); const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false); const [err, setErr] = useState(null); const [msg, setMsg] = useState(null)
  const reset = () => { setQuery(''); setResolved(null); setCandidates([]); setManual(false); setQty(''); setAvg(''); setAvgCur('EUR'); setBuyDate(''); setNote(''); setErr(null) }

  const doResolve = async (q) => {
    setErr(null); setMsg(null); setResolving(true); setCandidates([])
    const { data, error } = await resolveIsin(q)
    setResolving(false)
    if (error) { setErr(error.message); return }
    if (data?.resolved) { setResolved({ ticker: data.ticker, name: data.name, currency: data.currency, exchange: data.exchange, isin: data.isin }); setManual(false) }
    else if (data?.ambiguous) setCandidates(data.candidates || [])
    else { setManual(true); setResolved(null) }
  }
  const doSave = async () => {
    if (!resolved?.ticker || !(Number(qty) > 0)) { setErr('Serve strumento risolto e quantità > 0.'); return }
    setBusy(true); setErr(null)
    const { error } = await saveHolding({ ticker: resolved.ticker, isin: resolved.isin || null, name: resolved.name || null, currency: resolved.currency || null, exchange: resolved.exchange || null, quantity: Number(qty), avg_price: avg === '' ? null : Number(avg), avg_price_currency: avgCur, buy_date: buyDate || null, note: note || null })
    setBusy(false)
    if (error) { setErr(error.message); return }
    setMsg(`${resolved.ticker} salvato.`); reset(); onSaved?.()
  }
  return (
    <section className="panel">
      <header className="panel-head"><h2>Aggiungi una posizione</h2><span className="muted small">per ISIN o ticker · conferma nome e valuta</span></header>
      {!apiConfigured && <p className="muted small">Configura l'API locale per risolvere ISIN e salvare.</p>}
      <div className="desk-controls">
        <label>ISIN o ticker<input value={query} onChange={(e) => setQuery(e.target.value.trim())} placeholder="es. US5949181045 o MSFT" /></label>
        <button className="ghost small" disabled={!query || resolving || !apiConfigured} onClick={() => doResolve(query)}>{resolving ? 'Cerco…' : '🔎 Risolvi'}</button>
      </div>
      {candidates.length > 0 && <div className="conc-block"><p className="muted small">Più corrispondenze:</p>{candidates.map((c) => <button key={c.symbol} className="ghost small candidate" onClick={() => doResolve(c.symbol)}><strong>{c.symbol}</strong> · {c.name || '—'}{c.exchange ? ` · ${c.exchange}` : ''}</button>)}</div>}
      {manual && !resolved && <p className="gate-line gate-warn"><span className="gate-tag">⚠ non risolto</span> digita il <strong>ticker</strong> yfinance e premi Risolvi.</p>}
      {resolved && (
        <div className="resolved-box">
          <p className="ok small">Confermi: <strong>{resolved.name || resolved.ticker}</strong> · {resolved.ticker} · <strong>{resolved.currency || 'n/d'}</strong></p>
          <div className="paper-fields">
            <label>Quantità<input type="number" step="any" value={qty} onChange={(e) => setQty(e.target.value)} /></label>
            <label>Prezzo di carico (in {avgCur})<input type="number" step="any" value={avg} onChange={(e) => setAvg(e.target.value)} /></label>
            <label>Valuta del carico<select value={avgCur} onChange={(e) => setAvgCur(e.target.value)}><option value="EUR">EUR (di conto)</option>{resolved.currency && resolved.currency !== 'EUR' && <option value={resolved.currency}>{resolved.currency} (di quotazione)</option>}</select></label>
            <label>Data acquisto<input type="date" value={buyDate} onChange={(e) => setBuyDate(e.target.value)} /></label>
            <label>Note<input value={note} onChange={(e) => setNote(e.target.value)} /></label>
          </div>
          <div className="form-actions"><button className="primary" disabled={busy} onClick={doSave}>{busy ? 'Salvo…' : '＋ Salva'}</button><button className="ghost small" disabled={busy} onClick={reset}>Annulla</button></div>
        </div>
      )}
      {err && <p className="error">{err}</p>}
      {msg && <p className="ok small">{msg}</p>}
    </section>
  )
}

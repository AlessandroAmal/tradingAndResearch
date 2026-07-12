import { useMemo } from 'react'
import { themeConcentration, themesBySymbol } from '../lib/concentration'
import { fmtNum, fmtPct } from '../lib/format'

// THEMATIC CONCENTRATION — a real risk the book can hide. Positions on different
// tickers (MSFT/AVGO/VRT/NVDA/GOOGL) can be one bet on AI/data-center capex: in a
// de-rating they fall together. READ-ONLY warning, never a trade or a direction.
export default function ConcentrationWarning({ positions, priceBySymbol, multiplierBySymbol, instruments }) {
  const themed = useMemo(() => {
    const bySym = themesBySymbol(instruments)
    const pos = (positions || []).map((p) => {
      const price = priceBySymbol?.[p.symbol] ?? p.entry
      const mult = multiplierBySymbol?.[p.symbol] ?? 1
      return { symbol: p.symbol, notional: Math.abs(Number(p.size) * Number(price) * mult) || 0 }
    })
    return themeConcentration(pos, bySym)
  }, [positions, priceBySymbol, multiplierBySymbol, instruments])

  const flagged = themed.filter((t) => t.concentrated)
  if (flagged.length === 0) return null

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>Concentrazione tematica</h2>
        <span className="muted small">diversificazione apparente ≠ reale</span>
      </header>
      {flagged.map((t) => (
        <p key={t.theme} className="gate-line gate-warn">
          <span className="gate-tag">⚠ {t.label}</span>
          <strong>{t.positions} posizioni</strong> sullo stesso tema
          {t.weight != null ? <> (<strong>{fmtPct(t.weight * 100).replace('+', '')}</strong> del book</> : null}
          {t.weight != null ? <>, {fmtNum(t.notional, 0)})</> : <> ({fmtNum(t.notional, 0)})</>}:
          {' '}{t.symbols.join(', ')} — sono <strong>correlate</strong>: in un de-rating della tesi scendono INSIEME.
          La diversificazione apparente non è reale.
        </p>
      ))}
      <p className="muted small caveat">Peso calcolato per esposizione (size × prezzo × point value). È un avviso di rischio, non una direzione né un ordine.</p>
    </section>
  )
}

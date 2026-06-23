import { useState } from 'react'
import { GUIDE_SECTIONS, GLOSSARY, UNIVERSE_GUIDE } from '../data/guide'

// Static reference page. Sections 0–8 + glossary, navigable as sub-tabs.
// Single source: texts come from src/data/guide.js (shared with the form
// tooltips, so the two never drift). Documentation only — read-only cockpit.
export default function Guide() {
  const tabs = [...GUIDE_SECTIONS, { id: 'glossario', label: 'A–Z · Glossario', glossary: true }]
  const [active, setActive] = useState(tabs[0].id)
  const current = tabs.find((t) => t.id === active) || tabs[0]

  return (
    <div className="guide">
      <p className="muted small">
        Guida di riferimento · cockpit informativo e di gestione del rischio · non è
        consulenza finanziaria · nessun ordine viene eseguito.
      </p>

      <nav className="nav guide-nav" aria-label="Sezioni della guida">
        {tabs.map((t) => (
          <button
            key={t.id}
            className={`nav-btn ${active === t.id ? 'active' : ''}`}
            onClick={() => setActive(t.id)}
            aria-current={active === t.id ? 'page' : undefined}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <section className="panel">
        {current.glossary ? (
          <dl className="guide-dl">
            {GLOSSARY.map((g) => (
              <div className="guide-row" key={g.term}>
                <dt>{g.term}</dt>
                <dd>{g.body}</dd>
              </div>
            ))}
          </dl>
        ) : (
          current.blocks.map((b, i) => <Block key={i} block={b} />)
        )}
      </section>
    </div>
  )
}

function Block({ block }) {
  switch (block.type) {
    case 'p':
      return <p className="guide-p">{block.text}</p>
    case 'h':
      return <h3 className="guide-h">{block.text}</h3>
    case 'note':
      return <p className="banner note small">{block.text}</p>
    case 'ul':
      return (
        <ul className="guide-ul">
          {block.items.map((it, i) => <li key={i}>{it}</li>)}
        </ul>
      )
    case 'dl':
      return (
        <dl className="guide-dl">
          {block.items.map((it) => (
            <div className="guide-row" key={it.term}>
              <dt>{it.term}</dt>
              <dd>{it.def}</dd>
            </div>
          ))}
        </dl>
      )
    case 'universe':
      return (
        <ul className="guide-universe">
          {UNIVERSE_GUIDE.map((i) => (
            <li key={i.symbol} className="guide-inst">
              <div className="guide-inst-head">
                <span className="sym">{i.symbol}</span>
                <span className="name">{i.name}</span>
                <span className={`pill sleeve-${i.sleeve}`}>{i.sleeve}</span>
                {i.traded === false && <span className="pill pill-gauge">gauge · non tradato</span>}
              </div>
              <div className="muted small">Tradeable on: {i.tradeableOn}</div>
              <div className="guide-why">{i.why}</div>
            </li>
          ))}
        </ul>
      )
    default:
      return null
  }
}

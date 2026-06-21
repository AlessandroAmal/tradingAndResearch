import {
  FIELD_HELP,
  UNIVERSE_GUIDE,
  RISK_CONCEPTS,
  RISK_PHASE_NOTE,
  GLOSSARY,
} from '../data/guide'

// Static reference page. Documentation only — read-only cockpit.
export default function Guide() {
  return (
    <div className="guide">
      <p className="muted small">
        Guida di riferimento · cockpit informativo e di gestione del rischio ·
        non è consulenza finanziaria · nessun ordine viene eseguito.
      </p>

      {/* a. Parametri posizione */}
      <section className="panel">
        <header className="panel-head"><h2>Parametri posizione</h2></header>
        <dl className="guide-dl">
          {FIELD_HELP.map((f) => (
            <div className="guide-row" key={f.key}>
              <dt>{f.label}</dt>
              <dd>{f.text}</dd>
            </div>
          ))}
        </dl>
      </section>

      {/* b. Concetti di rischio */}
      <section className="panel">
        <header className="panel-head"><h2>Concetti di rischio</h2></header>
        <dl className="guide-dl">
          {RISK_CONCEPTS.map((c) => (
            <div className="guide-row" key={c.title}>
              <dt>{c.title}</dt>
              <dd>{c.body}</dd>
            </div>
          ))}
        </dl>
        <p className="banner note small">{RISK_PHASE_NOTE}</p>
      </section>

      {/* c. Universo strumenti */}
      <section className="panel">
        <header className="panel-head"><h2>Universo strumenti</h2></header>
        <ul className="guide-universe">
          {UNIVERSE_GUIDE.map((i) => (
            <li key={i.symbol} className="guide-inst">
              <div className="guide-inst-head">
                <span className="sym">{i.symbol}</span>
                <span className="name">{i.name}</span>
                <span className={`pill sleeve-${i.sleeve}`}>{i.sleeve}</span>
                {i.traded === false && (
                  <span className="pill pill-gauge">gauge · non tradato</span>
                )}
              </div>
              <div className="muted small">Tradeable on: {i.tradeableOn}</div>
              <div className="guide-why">{i.why}</div>
            </li>
          ))}
        </ul>
      </section>

      {/* d. Glossario statistiche */}
      <section className="panel">
        <header className="panel-head"><h2>Glossario statistiche</h2></header>
        <dl className="guide-dl">
          {GLOSSARY.map((g) => (
            <div className="guide-row" key={g.term}>
              <dt>{g.term}</dt>
              <dd>{g.body}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  )
}

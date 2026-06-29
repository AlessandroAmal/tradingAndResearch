// One-line PURPOSE + a collapsible "come si usa" for each non-decision tab, to
// lower the sense of complexity. Read-only orientation; links to the Guida.
export default function TabHeader({ title, purpose, howto = [], onGuide }) {
  return (
    <section className="panel tabhead">
      <div className="tabhead-row">
        <div>
          <h2 className="tabhead-title">{title}</h2>
          <p className="tabhead-purpose">{purpose}</p>
        </div>
        {onGuide && <button className="ghost small" onClick={onGuide}>Guida ↗</button>}
      </div>
      {howto.length > 0 && (
        <details className="tabhead-howto">
          <summary>Come si usa</summary>
          <ul className="tight">{howto.map((h, i) => <li key={i} className="muted small">{h}</li>)}</ul>
        </details>
      )}
    </section>
  )
}

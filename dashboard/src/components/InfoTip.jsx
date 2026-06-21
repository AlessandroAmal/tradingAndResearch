// Inline "i" info icon with an accessible tooltip.
// Shown on hover and keyboard focus via CSS — no JS state, no storage.
export default function InfoTip({ text, label }) {
  const aria = label ? `${label}: ${text}` : text
  return (
    <span className="infotip" tabIndex={0} role="note" aria-label={aria}>
      <span className="infotip-icon" aria-hidden="true">i</span>
      <span className="infotip-bubble" role="tooltip">{text}</span>
    </span>
  )
}

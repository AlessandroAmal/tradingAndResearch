// Shared "livello scelto" price input (AUDIT2 §6.A #6) — the one control the user
// types a price level into, previously duplicated in the decision board (top band
// + implied panel) and in Prospettive. Pure presentational: each view keeps its
// OWN implied-odds computation (board's option-implied vs prospects' options-vs-
// history) because the data differs — only the input is shared, no behaviour change.
export default function LevelInput({
  value, onChange, placeholder = 'prezzo',
  label = 'Il tuo livello (prezzo)', labelClass = '',
}) {
  return (
    <label className={labelClass}>{label}
      <input type="number" step="any" inputMode="decimal" value={value}
        onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
    </label>
  )
}

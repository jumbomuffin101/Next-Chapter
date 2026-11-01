// Accessible tab row (arrow keys, Home, End), same pattern as the alumni dashboard
export default function Tabs({ tabs, active, onChange, label, panelId, className = 'alumni-tabs' }) {
  function onKeyDown(event, key) {
    const keys = tabs.map(([k]) => k)
    let next
    if (event.key === 'ArrowRight') next = keys[(keys.indexOf(key) + 1) % keys.length]
    if (event.key === 'ArrowLeft') next = keys[(keys.indexOf(key) + keys.length - 1) % keys.length]
    if (event.key === 'Home') next = keys[0]
    if (event.key === 'End') next = keys[keys.length - 1]
    if (next) { event.preventDefault(); onChange(next); document.getElementById(`tab-${next}`)?.focus() }
  }
  return <div className={className} role="tablist" aria-label={label}>{tabs.map(([key, text]) => <button key={key} id={`tab-${key}`} role="tab" aria-selected={active === key} aria-controls={panelId} tabIndex={active === key ? 0 : -1} onClick={() => onChange(key)} onKeyDown={event => onKeyDown(event, key)}>{text}</button>)}</div>
}

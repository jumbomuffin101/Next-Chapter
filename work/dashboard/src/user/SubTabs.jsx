// A row of square tabs inside a section. `tabs` is [[key, label], ...].
export default function SubTabs({ tabs, active, onChange, label }) {
  return <div className="sub-tabs" role="tablist" aria-label={label}>
    {tabs.map(([key, text]) => <button key={key} role="tab" aria-selected={active === key} onClick={() => onChange(key)}>{text}</button>)}
  </div>
}

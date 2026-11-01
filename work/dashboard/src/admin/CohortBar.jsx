// Pick which cohort every panel shows: Current, Next, a past cohort, or everyone.
export default function CohortBar({ cohorts, value, onChange }) {
  const current = cohorts?.current, next = cohorts?.next
  const past = (cohorts?.list ?? []).filter(item => item.year != null && current && item.year < Number(current))
  const isCurrent = value === 'current' || value === current
  const isNext = value === 'next' || value === next
  const pastValue = past.some(item => item.name === value) ? value : ''
  return <div className="cohort-bar" role="group" aria-label="Choose a cohort">
    <span className="cohort-label">Cohort</span>
    <button type="button" aria-pressed={isCurrent} onClick={() => onChange('current')}>Current{current ? ` · ${current}` : ''}</button>
    <button type="button" aria-pressed={isNext} onClick={() => onChange('next')}>Next{next ? ` · ${next}` : ''}</button>
    <select aria-label="Past cohorts" value={pastValue} onChange={event => event.target.value && onChange(event.target.value)} data-active={Boolean(pastValue)}>
      <option value="">Past cohorts…</option>
      {past.map(item => <option key={item.name} value={item.name}>{item.name} ({item.size})</option>)}
    </select>
    <button type="button" aria-pressed={value === 'all'} onClick={() => onChange('all')}>All cohorts</button>
  </div>
}

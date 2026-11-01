import { useEffect, useState } from 'react'
import { fetchCohortPeople } from '../api.js'
import Panel from './Panel.jsx'
import { growth, money, percent } from './format.js'

// The selected cohort at a glance: headline numbers, then everyone in it and what they do now.
export default function CohortInfo({ name, isCurrent, kpis, onBack }) {
  const [people, setPeople] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    fetchCohortPeople(name).then(items => { if (alive) { setPeople(items); setError('') } }, err => { if (alive) setError(err.message) })
    return () => { alive = false }
  }, [name])

  return <Panel collapsible title={isCurrent ? `Current cohort · ${name}` : `Cohort ${name}`} caption={isCurrent ? null : <button className="text-button" onClick={onBack}>← Back to current</button>} className="square">
    <dl className="cohort-stats">
      <div><dt>Alumni</dt><dd>{kpis.alumni}</dd></div>
      <div><dt>Employed</dt><dd>{percent(kpis.employment_rate)}</dd></div>
      <div><dt>Avg salary</dt><dd>{money(kpis.avg_salary)}</dd></div>
      <div><dt>Salary growth</dt><dd>{growth(kpis.salary_growth_pct)}</dd></div>
    </dl>
    {error && <p className="stage-error" role="alert">{error}</p>}
    {!people && !error && <p className="panel-empty">Loading people…</p>}
    {people?.length === 0 && <p className="panel-empty">No one is in this cohort yet.</p>}
    {people?.length > 0 && <ul className="people-list">{people.map(person => <li key={person.id}>
      <strong>{person.full_name || 'Name not added'}</strong>
      <small>{person.current_role ? `${person.current_role.title} · ${person.current_role.employer}` : 'No current role'}{person.city ? ` · ${person.city}` : ''}</small>
    </li>)}</ul>}
  </Panel>
}

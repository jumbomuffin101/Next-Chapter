import { useEffect, useState } from 'react'
import { fetchOutcomes } from '../api.js'
import OutcomeHeadline from './OutcomeHeadline.jsx'
import Panel from './Panel.jsx'
import { percent } from './format.js'

// Every cohort before the current one, newest first. Click one to load it into the cohort and map squares,
// and to see how that class has done in each year since graduating (the Outcomes tab, for one cohort).
export default function PastCohorts({ cohorts, selected, onSelect, onOpenOutcomes }) {
  const past = cohorts.list.filter(item => item.year != null && item.year < Number(cohorts.current))
  const picked = past.find(item => item.name === selected)
  return <Panel collapsible title="Past cohorts" caption={past.length ? 'Scroll sideways · click to view' : null} className="square">
    {past.length === 0 ? <p className="panel-empty">No past cohorts yet.</p> : <ul className="cohort-strip">
      {past.map(item => <li key={item.name}>
        <button type="button" aria-pressed={item.name === selected} onClick={() => onSelect(item.name)}>
          <strong>{item.name}</strong>
          <span>{item.size} alumni</span>
          <span>{item.size ? `${percent(item.employment_rate)} employed` : 'No data'}</span>
        </button>
      </li>)}
    </ul>}
    {picked ? <CohortOutcomes key={picked.name} cohort={picked.name} onOpen={() => onOpenOutcomes?.(picked.name)} />
      : past.length > 0 && <p className="panel-empty">Pick a cohort to see how it has done each year since graduating.</p>}
  </Panel>
}

function CohortOutcomes({ cohort, onOpen }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let alive = true
    fetchOutcomes(cohort).then(result => { if (alive) setData(result) }, err => { if (alive) setError(err.message) })
    return () => { alive = false }
  }, [cohort])
  if (error) return <p className="stage-error" role="alert">Couldn’t load outcomes: {error}</p>
  if (!data) return <p className="panel-empty">Loading outcomes for {cohort}…</p>
  return <div className="cohort-outcomes">
    <OutcomeHeadline rows={data.years} compact />
    <button type="button" className="text-button" onClick={onOpen}>See full outcomes for {cohort} →</button>
  </div>
}

import { useEffect, useState } from 'react'
import { fetchAdminDashboard } from '../api.js'
import ActionsPreview from './ActionsPreview.jsx'
import Automation from './Automation.jsx'
import Outcomes from './Outcomes.jsx'
import CohortInfo from './CohortInfo.jsx'
import MapPanel from './MapPanel.jsx'
import NeedsAction from './NeedsAction.jsx'
import PastCohorts from './PastCohorts.jsx'

// Four squares: the selected cohort and its map on top, past cohorts and the watch list below. Needs action is its own page.
export default function AdminDashboard({ onExpired }) {
  const [view, setView] = useState('overview') // 'overview' | 'outcomes' | 'actions' | 'automation'
  const [cohort, setCohort] = useState('current')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [tick, setTick] = useState(0)
  const [outcomesCohort, setOutcomesCohort] = useState('all') // which cohort the Outcomes tab opens on

  useEffect(() => {
    let alive = true
    fetchAdminDashboard(cohort).then(result => { if (alive) { setData(result); setError('') } },
      err => { if (err.status === 401) onExpired?.(); else if (alive) setError(err.message) })
    return () => { alive = false }
    // oxlint-disable-next-line react-hooks/exhaustive-deps -- reload on cohort/tick only; onExpired changes every render
  }, [cohort, tick])

  return <div className="tkh-app admin">
    <div className="admin-bar">
      <div className="view-tabs" role="tablist" aria-label="Admin pages">
        <button role="tab" aria-selected={view === 'overview'} onClick={() => setView('overview')}>Overview</button>
        <button role="tab" aria-selected={view === 'actions'} onClick={() => setView('actions')}>Needs action{data ? <b>{data.kpis.needs_action}</b> : null}</button>
        <button role="tab" aria-selected={view === 'outcomes'} onClick={() => setView('outcomes')}>Outcomes</button>
        <button role="tab" aria-selected={view === 'automation'} onClick={() => setView('automation')}>Automation sign ups</button>
      </div>
    </div>
    {error && <p className="stage-error" role="alert">Couldn’t load the dashboard: {error}</p>}
    {!data && !error && <p className="panel-empty">Loading live numbers…</p>}
    {data && view === 'overview' && <>
      <div className="admin-squares">
        <CohortInfo key={data.selected} name={data.selected} isCurrent={data.selected === data.cohorts.current} kpis={data.kpis} onBack={() => setCohort('current')} />
        <MapPanel locations={data.locations} />
        <PastCohorts cohorts={data.cohorts} selected={data.selected} onSelect={setCohort} onOpenOutcomes={name => { setOutcomesCohort(name); setView('outcomes') }} />
        <ActionsPreview items={data.actions_preview} total={data.kpis.needs_action} onOpen={() => setView('actions')} />
      </div>
      <p className="data-note">Demo records are synthetic; recorded roles and salaries are self-reported, not verified.</p>
    </>}
    {data && view === 'actions' && <NeedsAction cohort={cohort} onChanged={() => setTick(value => value + 1)} />}
    {data && view === 'outcomes' && <Outcomes key={outcomesCohort} cohorts={data.cohorts} initialCohort={outcomesCohort} onExpired={onExpired} />}
    {data && view === 'automation' && <Automation cohorts={data.cohorts} selected={data.selected} onExpired={onExpired} />}
  </div>
}

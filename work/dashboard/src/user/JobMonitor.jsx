import { useEffect, useState } from 'react'
import { fetchGrowth } from '../api.js'
import { SalaryForm } from './Growth.jsx'
import JobMatches from './JobMatches.jsx'
import Panel from '../admin/Panel.jsx'
import { ago, daysSince } from './recency.js'

const WINDOWS = [['week', 7, 'Updated this week'], ['month', 30, 'Updated this month'], ['any', null, 'Any time']]
const newestFirst = (a, b) => (Date.parse(b.updated_at) || 0) - (Date.parse(a.updated_at) || 0)

// Job monitor card: openings from live company job boards, matched to YOU, with how recent each one is.
export default function JobMonitor({ profile, jobs, refreshedAt, matchedOn, error, hasProfile, salaryVersion, onSalarySaved }) {
  const [hasSalary, setHasSalary] = useState(null)
  const [window_, setWindow_] = useState('any')
  const [sort, setSort] = useState('best')
  const [now] = useState(() => Date.now())
  const load = () => fetchGrowth().then(data => setHasSalary(data.salary_history.length > 0), () => setHasSalary(null))
  useEffect(() => { load() }, [salaryVersion])

  const inWindow = days => jobs.filter(job => { const age = daysSince(job.updated_at, now); return days == null || (age !== null && age <= days) })
  const limit = WINDOWS.find(([key]) => key === window_)[1]
  const shown = [...inWindow(limit)].sort(sort === 'newest' ? newestFirst : () => 0)
  const salary = matchedOn?.salary_min != null ? `$${matchedOn.salary_min.toLocaleString()}–$${matchedOn.salary_max.toLocaleString()}` : null

  return <Panel collapsible title="Job monitor" caption={jobs.length ? `${shown.length} of ${jobs.length} openings shown` : 'Fresh openings from live job boards'} className="monitor" id="card-jobs">
    <section className="personal-banner" aria-label="What these matches are based on">
      <span className="eyebrow">Personalized for you · based on your profile</span>
      {matchedOn ? <div className="signals">
        <span><small>Role</small>{matchedOn.role_title}</span>
        <span><small>Field</small>{matchedOn.role_type}</span>
        <span><small>Where</small>{matchedOn.city || 'Add your city'}</span>
        <span><small>Pay range</small>{salary || 'Add your salary'}</span>
      </div> : <p>Add your experience and city to get matches built around you.</p>}
      <p className="fresh-line"><Icon_ />Job list refreshed <b>{refreshedAt ? ago(refreshedAt, now) : 'recently'}</b>. Matches update when you update your profile.</p>
    </section>

    {hasSalary === false && <section className="prompt-banner">
      <div><h3>Add your salary for more accurate job matches</h3>
        <p>We rank jobs in your pay range first when a range is listed. Only you and the career team can see your salary.</p></div>
      <SalaryForm profile={profile} lead="Your annual salary range." onSaved={onSalarySaved ?? load} />
    </section>}

    {jobs.length > 0 && <div className="fresh-controls">
      <div className="chips" role="group" aria-label="How recently the job was updated">
        {WINDOWS.map(([key, days, label]) => <button key={key} aria-pressed={window_ === key} onClick={() => setWindow_(key)}>{label}<b>{inWindow(days).length}</b></button>)}
      </div>
      <label>Sort<select value={sort} onChange={event => setSort(event.target.value)}><option value="best">Best match first</option><option value="newest">Newest first</option></select></label>
    </div>}

    <JobMatches jobs={shown} error={error} hasProfile={hasProfile} now={now}
      emptyHint={jobs.length && !shown.length ? 'Nothing matched in that time window. Try “Any time”.' : undefined} />
  </Panel>
}

function Icon_() { return <span className="live-dot" aria-hidden="true" /> }

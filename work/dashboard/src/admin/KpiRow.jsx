import { NO_DATA, growth, money } from './format.js'

// The North Star numbers. Each tile says exactly what it counts; "recorded" never means "verified".
export default function KpiRow({ kpis, onNeedsAction }) {
  const k = kpis
  const tiles = [
    { label: 'Alumni records', value: k.alumni, sub: `${k.demo} demo · ${k.real} real`, hint: 'Profiles in the selected cohort' },
    { label: 'Employed now', value: k.employment_rate == null ? '—' : `${k.employment_rate}%`, sub: `${k.employed} of ${k.alumni} have a current role`, hint: 'A recorded current role (not verified)' },
    { label: 'Salary growth', value: k.salary_growth_pct == null ? '—' : growth(k.salary_growth_pct), sub: k.salary_growth_pct == null ? 'Needs 2+ salary entries' : `avg of ${k.salary_growth_n} alumni · avg pay ${money(k.avg_salary)}`, hint: 'First vs latest recorded salary, alumni with 2+ entries' },
    { label: 'Participation', value: k.participation_pct == null ? '—' : `${k.participation_pct}%`, sub: `${k.participation_n} confirmed a resume in 180 days`, hint: 'Share who confirmed a resume in the last 180 days' },
    { label: 'Needs action', value: k.needs_action, sub: 'Open follow-ups · view list →', hint: 'Career gaps, missing info, stale resumes, help requests', action: onNeedsAction },
  ]
  return <div className="kpi-row" aria-label="North Star metrics">
    {tiles.map(tile => {
      const body = <><span className="kpi-label">{tile.label}</span><strong>{tile.value === NO_DATA ? '—' : tile.value}</strong><small>{tile.sub}</small></>
      return tile.action
        ? <button key={tile.label} className="kpi-tile action" onClick={tile.action} title={tile.hint}>{body}</button>
        : <div key={tile.label} className="kpi-tile" title={tile.hint}>{body}</div>
    })}
  </div>
}

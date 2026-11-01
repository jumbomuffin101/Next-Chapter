import { useEffect, useState } from 'react'
import { fetchOutcomes } from '../api.js'
import OutcomeHeadline from './OutcomeHeadline.jsx'
import Panel from './Panel.jsx'

const money = value => (value == null ? '—' : `$${Math.round(value).toLocaleString('en-US')}`)
const yearLabel = n => (n === 0 ? 'At graduation' : `${n} year${n === 1 ? '' : 's'}`)

// TKH's question: how are graduates doing three to five years after graduation? Employment and pay by years since
// graduation, across every cohort (or one), from the dated roles and salaries alumni record.
export default function Outcomes({ cohorts, initialCohort = 'all', onExpired }) {
  const [cohort, setCohort] = useState(initialCohort)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    fetchOutcomes(cohort).then(result => { if (alive) { setData(result); setError('') } },
      err => { if (err.status === 401) onExpired?.(); else if (alive) setError(err.message) })
    return () => { alive = false }
    // oxlint-disable-next-line react-hooks/exhaustive-deps -- reload on cohort only; onExpired changes every render
  }, [cohort])

  const years = (cohorts?.list ?? []).filter(item => item.year != null).map(item => item.name)
  return <div className="outcomes">
    <Panel title="Outcomes after graduation" caption="Employment and pay by years since graduation">
      <label className="auto-select">Cohort
        <select value={cohort} onChange={event => setCohort(event.target.value)}>
          <option value="all">All cohorts</option>
          {years.map(year => <option key={year} value={year}>{year}</option>)}
        </select>
      </label>
      {error && <p className="stage-error" role="alert">Couldn’t load outcomes: {error}</p>}
      {!data && !error && <p className="panel-empty">Loading outcomes…</p>}
      {data && <OutcomesBody data={data} />}
    </Panel>
  </div>
}

function OutcomesBody({ data }) {
  const rows = data.years
  return <>
    <OutcomeHeadline rows={rows} />
    <OutcomesChart rows={rows} />
    <table className="cohort-table outcomes-table">
      <thead><tr><th>Since graduation</th><th>Alumni</th><th>Employed</th><th>Median salary</th><th>Salary data from</th></tr></thead>
      <tbody>{rows.map(r => <tr key={r.years_out} className={r.years_out >= 3 && r.years_out <= 5 ? 'band' : ''}>
        <td><b>{yearLabel(r.years_out)}</b></td>
        <td>{r.alumni}</td>
        <td>{r.employed_pct == null ? '—' : `${r.employed_pct}%`}{r.with_work_history < r.alumni && r.alumni > 0 && <small> of {r.with_work_history} with history</small>}</td>
        <td>{money(r.median_salary)}</td>
        <td>{r.with_salary} alumni</td>
      </tr>)}</tbody>
    </table>
    <p className="data-note">Graduation is taken as July 1 of the graduation year (only the year is stored). “Employed” means a recorded role covers that date; alumni with no work history recorded are left out rather than counted as unemployed. Salaries are the midpoint of self-reported ranges. {data.demo > 0 && `${data.demo} of ${data.alumni} records are synthetic demo data, not verified TKH outcomes.`}</p>
  </>
}

// Bars: % employed. Line: median salary. The 3–5 year band is shaded.
function OutcomesChart({ rows }) {
  const W = 960, H = 280, left = 20, right = 20, top = 42, bottom = 30
  const plotW = W - left - right, plotH = H - top - bottom
  const step = plotW / rows.length
  const x = i => left + step * i + step / 2
  const pays = rows.map(r => r.median_salary).filter(v => v != null)
  const hi = Math.max(...pays, 1) * 1.1
  const yPct = pct => top + plotH - (pct / 100) * plotH
  const yPay = value => top + plotH - (value / hi) * plotH
  const line = rows.map((r, i) => (r.median_salary == null ? null : `${x(i)},${yPay(r.median_salary)}`)).filter(Boolean).join(' ')
  const bandStart = rows.findIndex(r => r.years_out === 3), bandEnd = rows.findIndex(r => r.years_out === 5)
  return <svg className="outcomes-chart" viewBox={`0 0 ${W} ${H}`} role="img"
    aria-label={`By years since graduation: ${rows.map(r => `${yearLabel(r.years_out)}: ${r.employed_pct ?? 'no'}% employed, median ${money(r.median_salary)}`).join('; ')}`}>
    {bandStart >= 0 && bandEnd >= 0 && <>
      <rect className="band" x={left + step * bandStart} y={top - 14} width={step * (bandEnd - bandStart + 1)} height={plotH + 14} />
      <text className="band-label" x={left + step * (bandStart + (bandEnd - bandStart + 1) / 2)} y={top - 3} textAnchor="middle">3–5 years out</text>
    </>}
    <line className="axis" x1={left} x2={W - right} y1={top + plotH} y2={top + plotH} />
    {rows.map((r, i) => <g key={r.years_out}>
      {r.employed_pct != null && <rect className="bar" x={x(i) - step * 0.28} y={yPct(r.employed_pct)} width={step * 0.56} height={top + plotH - yPct(r.employed_pct)} />}
      {r.employed_pct != null && <text className="bar-label" x={x(i)} y={top + plotH - 8} textAnchor="middle">{r.employed_pct}%</text>}
      <text x={x(i)} y={H - 8} textAnchor="middle">{r.years_out === 0 ? 'At graduation' : `${r.years_out} year${r.years_out === 1 ? '' : 's'}`}</text>
    </g>)}
    {line && <polyline className="pay-line" points={line} />}
    {rows.map((r, i) => r.median_salary != null && <g key={`p${r.years_out}`}>
      <circle className="pay-dot" cx={x(i)} cy={yPay(r.median_salary)} r="5" />
      <text className="pay-label" x={x(i)} y={yPay(r.median_salary) - 9} textAnchor="middle">${Math.round(r.median_salary / 1000)}k</text>
    </g>)}
    <text className="legend" x={left} y={14}>■ % employed (in the bar)</text>
    <text className="legend pay" x={left + 190} y={14}>● median salary</text>
  </svg>
}

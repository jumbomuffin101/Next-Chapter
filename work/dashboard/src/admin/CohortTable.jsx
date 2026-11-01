import Panel from './Panel.jsx'
import { growth, money, percent } from './format.js'

// Every cohort side by side. Click a row to look at that cohort.
export default function CohortTable({ cohorts, selected, onSelect }) {
  return <Panel title="Compare cohorts" caption="Click a row to view that cohort" className="span-7">
    <table className="cohort-table">
      <thead><tr><th>Cohort</th><th>Alumni</th><th>Employed</th><th>Avg salary</th><th>Salary growth</th></tr></thead>
      <tbody>{cohorts.list.map(item => <tr key={item.name} aria-selected={item.name === selected} onClick={() => onSelect(item.name)} tabIndex={0}
        onKeyDown={event => { if (event.key === 'Enter') onSelect(item.name) }}>
        <td><b>{item.name}</b>{item.name === cohorts.current && <em>current</em>}{item.name === cohorts.next && <em>next</em>}</td>
        <td>{item.size}</td><td>{item.size ? percent(item.employment_rate) : '—'}</td><td>{money(item.avg_salary)}</td><td>{growth(item.salary_growth_pct)}</td>
      </tr>)}</tbody>
    </table>
  </Panel>
}

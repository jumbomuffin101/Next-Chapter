import Panel from './Panel.jsx'
import { money } from './format.js'

const periodText = period => { const [year, quarter] = period.split('-'); return `${quarter} ${year.slice(2)}` }

// Average salary over time for the cohort (one point per quarter), plus where today's salaries fall.
export default function SalaryPanel({ salary }) {
  const { series, distribution, n_with_salary: n } = salary
  const W = 560, H = 190, padX = 52, padY = 34
  const values = series.map(point => point.avg)
  const lo = Math.min(...values), hi = Math.max(...values), span = hi - lo || 1
  const x = i => (series.length === 1 ? W / 2 : padX + (i * (W - padX * 2)) / (series.length - 1))
  const y = value => H - padY - ((value - lo) / span) * (H - padY * 2)
  const top = Math.max(...distribution.map(bin => bin.count), 1)
  return <Panel title="Salary progression" caption={n ? `${n} ${n === 1 ? 'alumnus' : 'alumni'} with salary data` : 'No salary data yet'} className="span-8">
    {series.length === 0 ? <p className="panel-empty">No one in this cohort has recorded a salary yet. Salary progression appears as alumni add theirs.</p> : <>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Average salary by quarter">
        <line className="axis" x1={padX} x2={W - padX} y1={H - padY} y2={H - padY} />
        {series.length > 1 && <polyline className="line" points={series.map((point, i) => `${x(i)},${y(point.avg)}`).join(' ')} />}
        {series.map((point, i) => <g key={point.period}>
          <rect className="dot" x={x(i) - 6} y={y(point.avg) - 6} width="12" height="12"><title>{`${point.period}: ${money(point.avg)} average, ${point.n} alumni`}</title></rect>
          <text x={x(i)} y={y(point.avg) - 14} textAnchor="middle">{money(point.avg)}</text>
          <text x={x(i)} y={H - 12} textAnchor="middle" className="muted">{periodText(point.period)}</text>
          <text x={x(i)} y={H - 1} textAnchor="middle" className="muted small">n={point.n}</text>
        </g>)}
      </svg>
      <h3 className="mini-title">Where salaries sit today</h3>
      <ul className="bars">{distribution.map(bin => <li key={bin.label}>
        <span>{bin.label}</span><div><i style={{ width: `${(bin.count / top) * 100}%` }} /></div><b>{bin.count}</b>
      </li>)}</ul>
    </>}
  </Panel>
}

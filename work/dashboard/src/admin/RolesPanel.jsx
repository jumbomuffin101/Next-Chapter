import Panel from './Panel.jsx'

const COLORS = ['#2b1f5e', '#fcc419', '#6b5fd0', '#c3c1f7', '#8f84e8', '#4a3a99', '#e0a800', '#9a97c8']

function slice(cx, cy, r, from, to) {
  const point = angle => [cx + r * Math.sin(angle), cy - r * Math.cos(angle)]
  const [x1, y1] = point(from), [x2, y2] = point(to)
  return `M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${to - from > Math.PI ? 1 : 0} 1 ${x2},${y2} Z`
}

// Types of roles: the role family of each alumnus's current (or newest) job.
export default function RolesPanel({ roles }) {
  const total = roles.reduce((sum, role) => sum + role.count, 0)
  let angle = 0
  return <Panel title="Types of roles" caption={total ? `${total} alumni with a role on record` : 'No roles yet'} className="span-4">
    {total === 0 ? <p className="panel-empty">No roles on record for this cohort yet.</p> : <div className="pie-wrap">
      <svg viewBox="0 0 120 120" className="pie" role="img" aria-label="Share of alumni by role type">
        {roles.length === 1
          ? <circle cx="60" cy="60" r="56" fill={COLORS[0]} />
          : roles.map((role, i) => { const from = angle; angle += (role.count / total) * Math.PI * 2
              return <path key={role.family} d={slice(60, 60, 56, from, angle)} fill={COLORS[i % COLORS.length]} stroke="#fff" strokeWidth="1.5"><title>{`${role.label}: ${role.count}`}</title></path> })}
      </svg>
      <ul className="legend">{roles.map((role, i) => <li key={role.family}><i style={{ background: COLORS[i % COLORS.length] }} />{role.label}<b>{role.count} · {Math.round((role.count / total) * 100)}%</b></li>)}</ul>
    </div>}
  </Panel>
}

import { useEffect, useState } from 'react'
import { addSalary, fetchGrowth, removeSalary, setSalaryJob } from '../api.js'

const money = value => `$${Math.round(value).toLocaleString('en-US')}`
const dateText = value => new Date(`${value}T12:00:00`).toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
const midpoint = record => (record.salary_min != null && record.salary_max != null ? (record.salary_min + record.salary_max) / 2 : null)

const thisMonth = () => { const now = new Date(); return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}` } // local, not UTC

// Records what you earned in a month: this month by default, or any past month to fill in your history.
export function SalaryForm({ onSaved, lead }) {
  const [form, setForm] = useState({ min: '', max: '', month: thisMonth() })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  async function submit(event) {
    event.preventDefault()
    const min = Number(form.min), max = Number(form.max)
    if (!Number.isInteger(min) || !Number.isInteger(max) || min <= 0 || max <= 0) return setError('Enter both numbers as whole dollar amounts.')
    if (min > max) return setError('The minimum can’t be higher than the maximum.')
    if (!/^\d{4}-\d{2}$/.test(form.month) || form.month > thisMonth()) return setError('Pick the month you earned this (not in the future).')
    setError(''); setSaving(true)
    try { await addSalary({ min, max, month: form.month }); setForm({ min: '', max: '', month: thisMonth() }); await onSaved() }
    catch (err) { setError(err.message) }
    finally { setSaving(false) }
  }

  return <form className="growth-unlock" onSubmit={submit}>
    <p className="sub" style={{ margin: 0 }}>{lead} <span className="badge-rec">Recommended</span></p>
    <div className="salary-row">
      <label className="field-big"><span>Minimum ($ / year)</span><input inputMode="numeric" placeholder="70000" value={form.min} onChange={event => setForm({ ...form, min: event.target.value.replace(/[^\d]/g, '') })} /></label>
      <label className="field-big"><span>Maximum ($ / year)</span><input inputMode="numeric" placeholder="90000" value={form.max} onChange={event => setForm({ ...form, max: event.target.value.replace(/[^\d]/g, '') })} /></label>
    </div>
    <label className="field-big salary-month"><span>When (month you earned this)</span>
      <input type="month" max={thisMonth()} value={form.month} onChange={event => setForm({ ...form, month: event.target.value })} /></label>
    <p className="note-box" style={{ margin: 0 }}>Only you and the TKH career team can see this. The admin dashboard shows averages across alumni, never your individual number.</p>
    {error && <p className="stage-error" role="alert">{error}</p>}
    <div><button className="primary-button" disabled={saving}>{saving ? 'Saving…' : 'Save salary'}</button></div>
  </form>
}

// Salary over time from the stored records (nothing is estimated), with the full history listed under the chart.
// salaryVersion changes whenever a salary is saved anywhere on the page; onChanged tells the page this card changed one.
export default function Growth({ salaryVersion, onChanged }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const load = () => fetchGrowth().then(setData, err => setError(err.message))
  useEffect(() => { load() }, [salaryVersion])

  if (error) return <div className="growth-card"><p className="stage-error">We couldn’t load your growth data: {error}</p></div>
  if (!data) return <div className="growth-card"><p>Loading your growth data…</p></div>

  const points = data.salary_history.filter(record => midpoint(record) != null && record.date)
  const values = points.map(midpoint)
  const change = points.length >= 2 ? Math.round(((values.at(-1) - values[0]) / values[0]) * 100) : null
  return <div className="growth-card">
    {change != null ? <>
      <h3>Pay change since {dateText(points[0].date)}</h3>
      <div className="growth-delta">{change >= 0 ? '+' : ''}{change}%</div>
      <p style={{ margin: '8px 0 0' }}>From {money(values[0])} to {money(values.at(-1))} (midpoint of your salary range).</p>
    </> : points.length === 1 ? <>
      <h3>Your salary range</h3>
      <div className="growth-delta">{money(points[0].salary_min)}–{money(points[0].salary_max)}</div>
      <p style={{ margin: '8px 0 0' }}>Recorded {dateText(points[0].date)}. Add a new range when your pay changes and the chart shows your growth.</p>
    </> : <h3>Your salary over time</h3>}
    <SalaryChart points={points} />
    <SalaryHistory points={points} jobs={data.jobs ?? []} onChanged={next => { setData(next); onChanged?.() }} />
    <div style={{ marginTop: 24 }}>
      <SalaryForm onSaved={onChanged ?? load} lead={points.length ? 'Add a raise, a new role, or a past salary you haven’t recorded yet.' : 'Add your current salary, and past ones too, to see how your pay has grown.'} />
    </div>
  </div>
}

// Each saved range is a bar from minimum to maximum with its midpoint marked; a line joins the midpoints over time.
// Always drawn: with no entries it shows an empty frame, with one entry a single bar.
function SalaryChart({ points }) {
  const W = 640, H = 220, padX = 56, padY = 36
  if (!points.length) return <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Salary chart, no salary added yet">
    <line className="axis" x1={padX} x2={W - padX} y1={H - padY} y2={H - padY} />
    <text x={W / 2} y={H / 2} textAnchor="middle">Your salary will appear here once you add a range.</text>
  </svg>
  const lo = Math.min(...points.map(p => p.salary_min)), hi = Math.max(...points.map(p => p.salary_max)), span = hi - lo || 1
  // spaced by real dates, so a two-year gap looks longer than a two-month one
  const times = points.map(p => Date.parse(p.date)), t0 = times[0], tSpan = times.at(-1) - t0
  const x = i => (points.length === 1 || !tSpan ? W / 2 : padX + ((times[i] - t0) / tSpan) * (W - padX * 2))
  const y = value => H - padY - ((value - lo) / span) * (H - padY * 2 - 24) - 12
  const mids = points.map(midpoint)
  return <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Salary over time: ${points.map(p => `${dateText(p.date)} ${money(midpoint(p))}`).join(', ')}`}>
    <line className="axis" x1={padX} x2={W - padX} y1={H - padY} y2={H - padY} />
    {points.length > 1 && <polyline className="line" points={mids.map((value, i) => `${x(i)},${y(value)}`).join(' ')} />}
    {points.map((point, i) => <g key={i}>
      <line className="range" x1={x(i)} x2={x(i)} y1={y(point.salary_min)} y2={y(point.salary_max)} />
      <rect className="dot" x={x(i) - 7} y={y(mids[i]) - 7} width="14" height="14" />
      <text x={x(i)} y={y(point.salary_max) - 10} textAnchor="middle">{money(mids[i])}</text>
      <text x={x(i)} y={H - 10} textAnchor="middle">{dateText(point.date)}</text>
    </g>)}
  </svg>
}

// Every recorded salary, newest first; your own entries can be removed (e.g. a typo or the wrong month).
function SalaryHistory({ points, jobs, onChanged }) {
  const [error, setError] = useState('')
  if (!points.length) return null
  async function remove(point) {
    setError('')
    try { onChanged(await removeSalary(point.date.slice(0, 7))) } catch (err) { setError(err.message) }
  }
  async function pickJob(point, jobId) {
    setError('')
    try { onChanged(await setSalaryJob(point.date.slice(0, 7), jobId || null)) } catch (err) { setError(err.message) }
  }
  return <div className="salary-history">
    <h4 className="mini-title">Salary history</h4>
    <ul>{[...points].reverse().map(point => <li key={point.date}>
      <span>{dateText(point.date)}</span>
      <b>{money(point.salary_min)} – {money(point.salary_max)}</b>
      {jobs.length > 0 && point.source === 'self_reported'
        ? <select className="salary-job" value={point.work_experience_id ?? ''} onChange={event => pickJob(point, event.target.value)}
            aria-label={`Job for the ${dateText(point.date)} salary`}>
            <option value="">Which job?</option>
            {jobs.map(job => <option key={job.id} value={job.id}>{job.label}</option>)}
          </select>
        : <span />}
      {point.source === 'self_reported'
        ? <button type="button" className="text-button" onClick={() => remove(point)} aria-label={`Remove the ${dateText(point.date)} salary`}>Remove</button>
        : <small>estimated</small>}
    </li>)}</ul>
    {error && <p className="stage-error" role="alert">{error}</p>}
  </div>
}

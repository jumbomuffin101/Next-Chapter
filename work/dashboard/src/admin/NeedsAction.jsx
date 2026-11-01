import { useEffect, useState } from 'react'
import { fetchActions, recordAction } from '../api.js'
import Panel from './Panel.jsx'

const FLAGS = [['', 'All', 'total'], ['career_gap', 'Career gap', 'career_gap'], ['missing_info', 'Missing info', 'missing_info'],
  ['stale', 'Stale resume', 'stale'], ['support', 'Asked for help', 'support']]
const STATUSES = [['open', 'Open'], ['contacted', 'Contacted'], ['resolved', 'Resolved'], ['all', 'All']]
const dateText = value => new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })

function Row({ item, onSaved }) {
  const [status, setStatus] = useState(item.status)
  const [note, setNote] = useState(item.note ?? '')
  const [saving, setSaving] = useState(false)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState('')
  const dirty = status !== item.status || note !== (item.note ?? '')

  async function save() {
    setSaving(true); setError('')
    try { await recordAction(item.id, { status, note }); await onSaved() }
    catch (err) { setError(err.message) }
    finally { setSaving(false) }
  }
  async function copy() {
    try { await navigator.clipboard.writeText(item.email); setCopied(true); setTimeout(() => setCopied(false), 1500) }
    catch { setError('Could not copy. Select the email and copy it by hand.') }
  }

  return <li className="action-row">
    <div className="who">
      <span className={`prio ${item.priority}`}>{item.priority}</span>
      <strong>{item.name}</strong>
      <small>{[item.cohort && `Cohort ${item.cohort}`, item.city].filter(Boolean).join(' · ') || 'No cohort or city'}</small>
      <button className="copy" onClick={copy} title="Copy email">{copied ? 'Copied ✓' : item.email}</button>
      <small>{item.last_confirmed ? `Last confirmed resume ${dateText(item.last_confirmed)}` : 'No confirmed resume'}</small>
    </div>
    <ul className="why">{item.flags.map(flag => <li key={flag.type}><b>{flag.label}</b><span>{flag.detail}</span></li>)}</ul>
    <div className="follow">
      <label>Status<select value={status} onChange={event => setStatus(event.target.value)}>
        <option value="open">Open</option><option value="contacted">Contacted</option><option value="resolved">Resolved</option></select></label>
      <label>Note<textarea rows="2" maxLength="1000" value={note} onChange={event => setNote(event.target.value)} placeholder="e.g. Emailed Oct 17, waiting to hear back" /></label>
      {error && <p className="stage-error" role="alert">{error}</p>}
      <button className="primary-button" disabled={!dirty || saving} onClick={save}>{saving ? 'Saving…' : 'Save follow-up'}</button>
      {item.last_action_at && <small>Last follow-up {dateText(item.last_action_at)}</small>}
    </div>
  </li>
}

// Everyone who needs attention, why, and what has been done about it. Nothing is emailed from here.
export default function NeedsAction({ cohort, onChanged }) {
  const [flag, setFlag] = useState('')
  const [status, setStatus] = useState('open')
  const [city, setCity] = useState('')
  const [q, setQ] = useState('')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let alive = true
    const timer = setTimeout(() => {
      fetchActions({ cohort, flag, status, city, q }).then(result => { if (alive) { setData(result); setError('') } }, err => { if (alive) setError(err.message) })
    }, q ? 250 : 0)
    return () => { alive = false; clearTimeout(timer) }
  }, [cohort, flag, status, city, q, tick])

  const refresh = async () => { setTick(value => value + 1); await onChanged?.() }

  return <div className="actions-page">
    <Panel title="Needs action" caption="Who may need a check-in or support, and why. Nothing is emailed from here.">
      <div className="filters">
        <div className="chips" role="group" aria-label="Filter by reason">
          {FLAGS.map(([value, label, key]) => <button key={label} aria-pressed={flag === value} onClick={() => setFlag(value)}>{label}<b>{data ? data.counts[key] : '…'}</b></button>)}
        </div>
        <label>Status<select value={status} onChange={event => setStatus(event.target.value)}>{STATUSES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>City<select value={city} onChange={event => setCity(event.target.value)}><option value="">All cities</option>{(data?.cities ?? []).map(name => <option key={name}>{name}</option>)}</select></label>
        <label>Search<input value={q} onChange={event => setQ(event.target.value)} placeholder="Name or email" /></label>
      </div>
      {error && <p className="stage-error" role="alert">{error}</p>}
      {data && data.items.length === 0 && <p className="panel-empty">{status === 'open' ? 'No open follow-ups match these filters.' : 'Nothing matches these filters.'}</p>}
      <ul className="action-list">{(data?.items ?? []).map(item => <Row key={`${item.id}-${item.status}-${item.last_action_at}`} item={item} onSaved={refresh} />)}</ul>
    </Panel>
  </div>
}

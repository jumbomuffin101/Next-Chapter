import { useEffect, useState } from 'react'
import QRCode from 'qrcode'
import { fetchAutomation, sendNewsletterToOne, setAutoEmails, setMonthlyNewsletter } from '../api.js'
import { roomLink } from '../landing/join.js'
import { appUrl } from '../user/mailto.js'
import Panel from './Panel.jsx'

const KINDS = [['just_joined', '“Just joined” to their cohort'], ['invite_worked', '“Your invite worked” to the inviter'],
  ['cohort_invite', 'Invites to classmates not on TKH yet']]
const when = value => (value ? new Date(value).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '—')

// 1. Peer invite emails run on their own when someone finishes onboarding. There is no send button: the only control is on/off.
function Emails({ emails, signups, onChanged }) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  async function toggle() {
    setSaving(true); setError('')
    try { await setAutoEmails(!emails.enabled); await onChanged() }
    catch (err) { setError(err.message) }
    finally { setSaving(false) }
  }
  return <Panel title="1 · Peer invite emails" caption={`${emails.total} logged · not sent`} className="span-6">
    <label className="auto-switch">
      <input type="checkbox" role="switch" checked={emails.enabled} disabled={saving} onChange={toggle} />
      <span><b>{emails.enabled ? 'On' : 'Off'}</b> · {emails.enabled
        ? 'When someone finishes onboarding, these emails are created automatically.'
        : 'Paused. New sign-ups don’t create any emails.'}</span>
    </label>
    {error && <p className="stage-error" role="alert">{error}</p>}
    <ul className="auto-counts">{KINDS.map(([kind, label]) => <li key={kind}><b>{emails.counts[kind]}</b>{label}</li>)}</ul>
    <p className="panel-empty">Emails are logged here, not sent: no mail provider is connected yet. Sign-ups so far through invite links: <b>{signups.invite}</b> · through the in-room QR: <b>{signups.room}</b>.</p>
    {emails.recent.length === 0 ? <p className="panel-empty">No automated emails yet. They appear when someone finishes onboarding.</p>
      : <ul className="outbox">{emails.recent.map(email => <li key={`${email.kind}-${email.to_email}-${email.created_at}`}>
        <details>
          <summary><span className="tag">{email.kind.replace('_', ' ')}</span><strong>{email.subject}</strong><small>To {email.to_name || email.to_email} · {when(email.created_at)}</small></summary>
          <p className="outbox-to">To: {email.to_email}</p>
          <pre>{email.body}</pre>
        </details>
      </li>)}</ul>}
  </Panel>
}

const SENT_MESSAGES = {
  dry_run: name => `Logged for ${name}. Dry run is on, so nothing was emailed.`,
  accepted: name => `Sent to ${name}.`,
  not_subscribed: name => `${name} hasn’t opted in to the newsletter, so nothing was sent. Alumni opt in from their dashboard.`,
}

// 2. Personalized newsletter: one digest per alum who opted in, monthly (on by default), or sent to one alum on demand.
function Newsletter({ newsletter, onChanged }) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [email, setEmail] = useState('')
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState('')
  async function toggle() {
    setSaving(true); setError('')
    try { await setMonthlyNewsletter(!newsletter.monthly_enabled); await onChanged() }
    catch (err) { setError(err.message) }
    finally { setSaving(false) }
  }
  async function send(event) {
    event.preventDefault()
    setSending(true); setError(''); setSent('')
    try {
      const result = await sendNewsletterToOne(email.trim())
      setSent((SENT_MESSAGES[result.status] ?? (() => `Status for ${result.name}: ${result.status}.`))(result.name))
      await onChanged()
    } catch (err) { setError(err.message) }
    finally { setSending(false) }
  }
  const dry = newsletter.mode === 'dry_run'
  const counts = Object.entries(newsletter.deliveries).map(([status, n]) => `${n} ${status.replace('_', ' ')}`).join(' · ')
  return <Panel title="2 · Personalized newsletter" caption="Next Chapter Monthly" className="span-6">
    <label className="auto-switch">
      <input type="checkbox" role="switch" checked={newsletter.monthly_enabled} disabled={saving} onChange={toggle} />
      <span><b>Send monthly · {newsletter.monthly_enabled ? 'On' : 'Off'}</b> · {newsletter.monthly_enabled
        ? 'Every alum who opted in gets their own digest on the 1st of the month at 9:00 AM ET: job matches, events and cohort news.'
        : 'Paused. The scheduled monthly run sends nothing until you turn this back on.'}</span>
    </label>
    {!newsletter.available && <p className="stage-error" role="alert">{newsletter.reason}</p>}
    <dl className="auto-facts">
      <div><dt>Mode</dt><dd>{dry ? 'Dry run' : 'Live'}</dd></div>
      <div><dt>Opted in</dt><dd>{newsletter.subscribers}</dd></div>
      <div><dt>Next monthly send</dt><dd>{when(newsletter.next_send_at)}</dd></div>
      <div><dt>This month</dt><dd>{counts || 'Nothing sent yet'}</dd></div>
    </dl>
    <p className="panel-empty">{dry ? 'Dry run: nothing is emailed until a sender is connected.' : 'Live: opted-in alumni on the delivery allowlist are emailed.'} Only demo accounts can get the newsletter for now.</p>
    <form className="auto-send" onSubmit={send}>
      <label className="auto-select">Send to one alum
        <input type="email" required placeholder="alum@example.com" value={email} onChange={event => setEmail(event.target.value)} />
      </label>
      <button className="primary-button" disabled={sending || !newsletter.available || !email.trim()}>{sending ? 'Sending…' : 'Send now'}</button>
    </form>
    {error && <p className="stage-error" role="alert">{error}</p>}
    {sent && <p className="demo-hint" role="status">{sent}</p>}
  </Panel>
}

// 3. Event QR codes: put one on the screen at an event; scanning it opens "Create profile" with the cohort already picked.
function RoomQr({ cohorts, selected }) {
  const years = (cohorts?.list ?? []).filter(item => item.year != null).map(item => item.name)
  const [cohort, setCohort] = useState(years.includes(selected) ? selected : cohorts?.current ?? years[0] ?? '')
  const [image, setImage] = useState('')
  const [error, setError] = useState('')
  const link = roomLink(appUrl(), cohort)
  useEffect(() => {
    let alive = true
    QRCode.toDataURL(link, { width: 640, margin: 1 }).then(url => { if (alive) { setImage(url); setError('') } },
      err => { if (alive) setError(`Couldn’t draw the QR code: ${err.message}`) })
    return () => { alive = false }
  }, [link])
  return <Panel title="3 · Event QR codes" caption="Show it on the screen at the event" className="span-12">
    <div className="room-qr">
      <div>
        <label className="auto-select">Cohort
          <select value={cohort} onChange={event => setCohort(event.target.value)}>{years.map(year => <option key={year} value={year}>{year}</option>)}</select>
        </label>
        <p className="panel-empty">Scanning opens <b>Create profile</b> with cohort <b>{cohort}</b> already picked. Sign-ups through it are counted above.</p>
        <p className="outbox-to">{link}</p>
        {error && <p className="stage-error" role="alert">{error}</p>}
      </div>
      {image && <img src={image} alt={`QR code to sign up for the TKH ${cohort} cohort`} />}
    </div>
  </Panel>
}

export default function Automation({ cohorts, selected, onExpired }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const load = () => fetchAutomation().then(result => { setData(result); setError('') },
    err => { if (err.status === 401) onExpired?.(); else setError(err.message) })
  // oxlint-disable-next-line react-hooks/exhaustive-deps -- load once; onExpired changes every render
  useEffect(() => { load() }, [])

  if (error) return <p className="stage-error" role="alert">Couldn’t load automation: {error}</p>
  if (!data) return <p className="panel-empty">Loading automation…</p>
  return <div className="admin-grid2">
    <Emails emails={data.emails} signups={data.signups} onChanged={load} />
    <Newsletter newsletter={data.newsletter} onChanged={load} />
    <RoomQr cohorts={cohorts} selected={selected} />
  </div>
}

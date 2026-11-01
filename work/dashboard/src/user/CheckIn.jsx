import { useState } from 'react'
import { getAlumniId } from '../api.js'
import { saveCheckIn } from './checkin.js'

// One-tap check-in: confirming takes one tap, so keeping the profile current doesn't feel like filling in a form.
// "Yes" re-confirms the saved profile on the server, which is what TKH's "updated recently" numbers count.
// The answer is remembered, so the dashboard doesn't ask again for a while (see checkin.js).
export default function CheckIn({ profile, savedDate, onConfirm, onNewRole, onLooking }) {
  const [answer, setAnswer] = useState(null) // 'yes' | 'new' | 'looking'
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const job = profile.work_experience.find(role => role.is_current)

  async function yes() {
    setBusy(true); setError('')
    try { await onConfirm(); setAnswer('yes'); saveCheckIn(getAlumniId(), 'yes') }
    catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }

  return <div className="checkin">
    <div className="checkin-question">
      <h3>{job ? `Still ${job.title} at ${job.employer}?` : 'Working somewhere new?'}</h3>
      <p>{savedDate && savedDate !== '—' ? `Last updated ${savedDate}. ` : ''}One tap keeps your profile, job matches and TKH’s picture of your career up to date.</p>
    </div>
    {answer === 'yes' ? <p className="checkin-done" role="status">✓ Thanks! Your role is confirmed.</p>
      : <div className="checkin-actions" role="group" aria-label="Check-in answer">
        {job && <button type="button" className="primary-button" disabled={busy} onClick={yes}>{busy ? 'Saving…' : 'Yes, same role'}</button>}
        <button type="button" className="secondary-button" onClick={() => { setAnswer('new'); saveCheckIn(getAlumniId(), 'new'); onNewRole() }}>I have a new role</button>
        <button type="button" className="secondary-button" onClick={() => { setAnswer('looking'); saveCheckIn(getAlumniId(), 'looking'); onLooking() }}>I’m looking</button>
      </div>}
    {error && <p className="stage-error" role="alert">{error}</p>}
  </div>
}

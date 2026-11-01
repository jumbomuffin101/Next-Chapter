import { useEffect, useState } from 'react'
import { fetchSupport, requestSupport } from '../api.js'

// "I'd like some help": tells the career team, who see it on their Needs action page.
export default function SupportBox() {
  const [message, setMessage] = useState('')
  const [sentAt, setSentAt] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { fetchSupport().then(result => setSentAt(result.requested_at), () => {}) }, [])

  async function send(event) {
    event.preventDefault()
    setBusy(true); setError('')
    try { const result = await requestSupport(message.trim()); setSentAt(result.requested_at); setMessage('') }
    catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }

  return <form className="support-box" onSubmit={send}>
    <div>
      <h3>Need a hand?</h3>
      <p>Between jobs, stuck, or want advice? Let the career team know and they’ll reach out. Add a note if you like.</p>
      {sentAt && <p className="sent">✓ Request sent {new Date(sentAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}. You can send another to update it.</p>}
    </div>
    <label className="field-big"><span>Optional note</span><textarea rows="3" maxLength="1000" value={message} onChange={event => setMessage(event.target.value)} placeholder="e.g. I'd like help preparing for interviews" /></label>
    {error && <p className="stage-error" role="alert">{error}</p>}
    <button className="primary-button" disabled={busy}>{busy ? 'Sending…' : sentAt ? 'Send another request' : 'Request support'}</button>
  </form>
}

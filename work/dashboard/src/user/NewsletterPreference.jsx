import { useEffect, useState } from 'react'
import { fetchNewsletterPreference, getNewsletterToken, updateNewsletterPreference } from '../api.js'

export default function NewsletterPreference({ onView }) {
  const [preference, setPreference] = useState(null)
  const [subscribed, setSubscribed] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const available = Boolean(getNewsletterToken())

  useEffect(() => {
    if (!available) return undefined
    let active = true
    fetchNewsletterPreference().then(result => {
      if (active) { setPreference(result); setSubscribed(result.subscribed) }
    }, err => { if (active) setError(err.message) })
    return () => { active = false }
  }, [available])

  async function save(event) {
    event.preventDefault()
    setSaving(true); setError(''); setMessage('')
    try {
      const result = await updateNewsletterPreference(subscribed)
      setPreference(result); setSubscribed(result.subscribed); setMessage(result.message)
    } catch (err) { setError(err.message) }
    finally { setSaving(false) }
  }

  return <section className="card" aria-labelledby="newsletter-heading" style={{ padding: 24, marginTop: 24 }}>
    <h2 id="newsletter-heading">Next Chapter Monthly</h2>
    <p>Your monthly career &amp; community digest: job opportunities, events, and cohort updates. Optional and separate from networking. Unsubscribe at any time.</p>
    {onView && <button type="button" className="primary-button newsletter-open" onClick={onView}>View Monthly Newsletter</button>}
    {!available ? <p>You can generate an in-app newsletter from a fictional profile after confirming it is synthetic. Email subscription preferences remain available only for signed demo accounts.</p> : <>
      {!preference && !error && <p role="status">Loading newsletter preference…</p>}
      {preference && <form onSubmit={save}>
        <label className="checkbox-field"><input type="checkbox" checked={subscribed} disabled={saving} onChange={event => { setSubscribed(event.target.checked); setMessage('') }} />I want to receive Next Chapter Monthly by email.</label>
        <p>Current preference: <strong>{preference.subscribed ? 'Subscribed' : 'Off'}</strong>. Delivery is limited to configured demo recipients.</p>
        <button className="primary-button" disabled={saving || subscribed === preference.subscribed}>{saving ? 'Saving…' : 'Save newsletter preference'}</button>
      </form>}
    </>}
    {error && <p className="form-error" role="alert">{error}</p>}
    {message && <p className="form-notice" role="status">{message}</p>}
  </section>
}

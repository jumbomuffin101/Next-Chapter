import { useState } from 'react'
import { signIn } from '../api.js'

// Email-only sign-in for now: opens the alumni profile for that email, or starts a new one.
export default function SignIn({ onSignedIn }) {
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setError(''); setBusy(true)
    try { onSignedIn(await signIn(email)) }
    catch (err) { setError(err.message); setBusy(false) }
  }

  return <div className="tkh-app profile-page">
    <form className="card profile-form" onSubmit={submit}>
      <section className="form-section">
        <h3>Welcome <span>back</span></h3>
        <p className="form-hint">Enter your email to open your alumni profile, or to start a new one.</p>
        <label className="form-field"><span>Email *</span><input type="email" required value={email} onChange={event => setEmail(event.target.value)} autoComplete="email" /></label>
      </section>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="profile-actions"><button type="submit" className="primary-button" disabled={busy}>{busy ? 'Signing in…' : 'Continue'}</button></div>
    </form>
  </div>
}

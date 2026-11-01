import { useEffect, useState } from 'react'
import logo from '../assets/tkh-logo.png'
import WaveArt from '../components/WaveArt.jsx'
import { adminLogin, alumniEnter, fetchInvite } from '../api.js'
import { readJoinParams } from './join.js'

// Role choice -> admin login (demo credentials) or alumni sign in / create profile.
// An invite link (?invite=) or the in-room QR code (?cohort=) opens straight on "Create profile".
export default function Landing({ onAdmin, onAlumni }) {
  const [join] = useState(() => readJoinParams(window.location.search))
  const joining = Boolean(join.invite || join.cohort)
  const [invitedBy, setInvitedBy] = useState(null) // { inviter_first_name, cohort }
  const [inviteError, setInviteError] = useState('')
  const [view, setView] = useState(joining ? 'alumni' : 'role') // 'role' | 'admin' | 'alumni'
  const [mode, setMode] = useState(joining ? 'signup' : 'signin') // alumni: 'signin' | 'signup'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState(null) // { text, fix?: { label, mode } }
  const [busy, setBusy] = useState(false)

  const go = next => { setView(next); setError(null); setBusy(false) }

  useEffect(() => { if (join.invite) fetchInvite(join.invite).then(setInvitedBy, err => setInviteError(err.message)) }, [join.invite])

  async function submitAdmin(event) {
    event.preventDefault()
    setError(null); setBusy(true)
    try { await adminLogin(email, password); onAdmin() }
    catch (err) { setError({ text: err.message }); setBusy(false) }
  }

  async function submitAlumni(event) {
    event.preventDefault()
    setError(null); setBusy(true)
    try {
      // an invite that didn't check out is not sent: the person signs up without it
      const user = await alumniEnter(mode, { email, fullName, invite: invitedBy ? join.invite : null, cohort: join.cohort })
      if (joining) window.history.replaceState(null, '', window.location.pathname) // the link has done its job
      onAlumni(user)
    }
    catch (err) {
      const fix = err.status === 404 ? { label: 'Create a profile', mode: 'signup' } : err.status === 409 ? { label: 'Sign in', mode: 'signin' } : null
      setError({ text: err.message, fix }); setBusy(false)
    }
  }

  return <div className="tkh-app stage-page" data-view={view}>
    <WaveArt />
    <span className="piece piece-a" /><span className="piece piece-b" /><span className="piece piece-c" />
    <header className="stage-brand"><img src={logo} alt="The Knowledge House" /></header>

    <main className="stage" key={`${view}-${mode}`}>
      {view === 'role' && <>
        <span className="eyebrow">Career mobility tracker</span>
        <h1>Welcome to The Knowledge House</h1>
        <p className="lede">What’s your role?</p>
        <div className="role-grid">
          <button className="role-card" onClick={() => go('admin')}>
            <strong>Admin</strong><span>Career team. See cohort outcomes, locations and who needs a check-in.</span><em className="go">Sign in →</em>
          </button>
          <button className="role-card" onClick={() => go('alumni')}>
            <strong>Alumni</strong><span>TKH graduate. Build your profile, track your growth and get matched to jobs.</span><em className="go">Get started →</em>
          </button>
        </div>
      </>}

      {view === 'admin' && <>
        <button className="link-back" onClick={() => go('role')}>← Back</button>
        <span className="eyebrow">Career team</span>
        <h2>Admin sign in</h2>
        <p className="lede">Sign in to see alumni outcomes across every cohort and city.</p>
        <form className="stage-form" onSubmit={submitAdmin}>
          <label className="field-big"><span>Email</span><input type="email" required autoFocus value={email} onChange={event => setEmail(event.target.value)} autoComplete="username" /></label>
          <label className="field-big"><span>Password</span><input type="password" required value={password} onChange={event => setPassword(event.target.value)} autoComplete="current-password" /></label>
          {error && <p className="stage-error" role="alert">{error.text}</p>}
          <button className="primary-button" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
          <p className="demo-hint">Demo access for now:<br /><code>admin@tkh.org</code> · <code>tkh-demo-2026</code></p>
        </form>
      </>}

      {view === 'alumni' && <>
        <button className="link-back" onClick={() => go('role')}>← Back</button>
        <span className="eyebrow">TKH alumni</span>
        <div className="seg" role="group" aria-label="Sign in or create a profile">
          <button type="button" aria-pressed={mode === 'signin'} onClick={() => { setMode('signin'); setError(null) }}>Sign in</button>
          <button type="button" aria-pressed={mode === 'signup'} onClick={() => { setMode('signup'); setError(null) }}>Create profile</button>
        </div>
        <p className="lede">{mode === 'signin' ? 'Welcome back. Enter your email to open your dashboard.' : 'New here? It takes about two minutes. All you need is your resume.'}</p>
        {mode === 'signup' && invitedBy && <p className="demo-hint">{invitedBy.inviter_first_name} invited you{invitedBy.cohort ? <> to join the <b>TKH {invitedBy.cohort}</b> cohort</> : null}. Create your profile and you’re in.</p>}
        {mode === 'signup' && join.cohort && <p className="demo-hint">Welcome, <b>TKH {join.cohort}</b> cohort! Create your profile and you’re in.</p>}
        {inviteError && <p className="stage-error" role="alert">{inviteError}</p>}
        <form className="stage-form" onSubmit={submitAlumni}>
          {mode === 'signup' && <label className="field-big"><span>Full name</span><input required autoFocus value={fullName} onChange={event => setFullName(event.target.value)} autoComplete="name" /></label>}
          <label className="field-big"><span>Email</span><input type="email" required autoFocus={mode === 'signin'} value={email} onChange={event => setEmail(event.target.value)} autoComplete="email" /></label>
          {error && <p className="stage-error" role="alert">{error.text}{error.fix && <> <button type="button" onClick={() => { setMode(error.fix.mode); setError(null) }}>{error.fix.label}</button></>}</p>}
          <button className="primary-button" disabled={busy}>{busy ? 'One moment…' : mode === 'signin' ? 'Sign in' : 'Create my profile'}</button>
        </form>
      </>}
    </main>
  </div>
}
